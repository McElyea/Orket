# Layer: integration

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_governed_agent_repository import (
    AsyncGovernedAgentRepository,
)
from orket.application.services.governed_agent_ports import (
    GovernedAgentInvocationBinding,
    GovernedAgentInvocationOutcome,
)
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, RunState
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)
from orket_extension_sdk.agent_fixtures import (
    agent_iteration_request,
    agent_iteration_result,
    agent_model_call_request,
    agent_model_call_result,
    prefixed_digest,
)

pytestmark = pytest.mark.integration


def _binding(request: dict[str, object]) -> GovernedAgentInvocationBinding:
    identity = request["identity"]
    assert isinstance(identity, dict)
    return GovernedAgentInvocationBinding(
        run_id=str(identity["run_id"]),
        attempt_id=str(identity["attempt_id"]),
        step_id=str(identity["step_id"]),
        iteration_ordinal=int(identity["iteration_ordinal"]),
        invocation_id=str(identity["invocation_id"]),
        fencing_generation=int(identity["fencing_generation"]),
        cancellation_epoch=0,
        deadline_utc=str(request["deadline_utc"]),
        extension_digest="sha256:" + "e" * 64,
        policy_digest=str(request["policy_digest"]),
        request_digest=prefixed_digest(request),
    )


async def _save_parent_authority(
    db_path: Path,
    binding: GovernedAgentInvocationBinding,
) -> AsyncControlPlaneExecutionRepository:
    repository = AsyncControlPlaneExecutionRepository(db_path)
    await repository.save_run_record(
        record=RunRecord(
            run_id=binding.run_id,
            workload_id="governed-agent-loop",
            workload_version="governed_agent_loop.v1",
            policy_snapshot_id="policy:agent-v1",
            policy_digest=binding.policy_digest,
            configuration_snapshot_id="config:agent-v1",
            configuration_digest="sha256:" + "c" * 64,
            creation_timestamp="2026-09-07T00:00:00Z",
            admission_decision_receipt_ref="admission:agent-1",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=binding.attempt_id,
        )
    )
    await repository.save_attempt_record(
        record=AttemptRecord(
            attempt_id=binding.attempt_id,
            run_id=binding.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="agent-state:initial",
            start_timestamp="2026-09-07T00:00:00Z",
        )
    )
    await repository.save_step_record(
        record=StepRecord(
            step_id=binding.step_id,
            attempt_id=binding.attempt_id,
            step_kind="governed_agent_iteration",
            input_ref=binding.request_digest,
            observed_result_classification="dispatch_prepared",
            closure_classification="step_open",
        )
    )
    return repository


@pytest.mark.asyncio
async def test_dispatch_and_result_publication_are_durable_and_compare_and_set(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.sqlite3"
    request = agent_iteration_request()
    binding = _binding(request)
    control_plane = await _save_parent_authority(db_path, binding)
    repository = AsyncGovernedAgentRepository(db_path)

    prepared = await repository.prepare_dispatch(binding=binding, request_payload=request)
    duplicate = await repository.prepare_dispatch(binding=binding, request_payload=request)
    restarted = AsyncGovernedAgentRepository(db_path)

    assert prepared.status == "prepared"
    assert duplicate.status == "idempotent"
    assert await restarted.get_dispatch_binding(invocation_id=binding.invocation_id) == binding
    assert (
        await restarted.prepare_dispatch(
            binding=replace(binding, fencing_generation=2),
            request_payload=request,
        )
    ).status == "conflict"

    result = _result_without_model_usage()
    outcome = GovernedAgentInvocationOutcome(
        status="returned",
        binding=binding,
        result_payload=result,
        result_digest=prefixed_digest(result),
        normalized_reason=None,
        child_confirmed_stopped=True,
    )
    accepted = await restarted.accept_result(outcome=outcome)
    replayed = await restarted.accept_result(outcome=outcome)
    conflicting_result = dict(result)
    conflicting_result["advisory_proposal"] = "different"
    conflict = await restarted.accept_result(
        outcome=replace(
            outcome,
            result_payload=conflicting_result,
            result_digest=prefixed_digest(conflicting_result),
        )
    )

    assert accepted.status == "accepted"
    assert replayed.status == "idempotent"
    assert conflict.status == "conflict"

    await _publish_and_assert_continuation(restarted, binding, outcome)

    run = await control_plane.get_run_record(run_id=binding.run_id)
    assert run is not None
    await control_plane.save_run_record(
        record=run.model_copy(update={"lifecycle_state": RunState.OPERATOR_BLOCKED})
    )
    assert (await restarted.accept_result(outcome=outcome)).status == "stale"


@pytest.mark.asyncio
async def test_broker_reservations_enforce_budget_and_retain_receipts_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "agent.sqlite3"
    iteration_request = agent_iteration_request()
    binding = _binding(iteration_request)
    await _save_parent_authority(db_path, binding)
    repository = AsyncGovernedAgentRepository(db_path)
    assert (await repository.prepare_dispatch(binding=binding, request_payload=iteration_request)).status == "prepared"

    call_request = agent_model_call_request()
    request_digest = prefixed_digest(call_request)
    reservation = await _reserve_model_call(repository, binding, call_request)
    uncertain_duplicate = await _reserve_model_call(repository, binding, call_request)

    assert reservation.status == "prepared"
    assert uncertain_duplicate.status == "uncertain"

    result = agent_model_call_result()
    record = await repository.complete_call(
        binding=binding,
        call_id=str(call_request["call_id"]),
        request_digest=request_digest,
        result_payload=result,
        result_digest=prefixed_digest(result),
        charged_input_tokens=128,
        charged_output_tokens=64,
    )
    retained = await _reserve_model_call(repository, binding, call_request)

    assert record.status == "completed"
    assert retained.status == "idempotent"
    assert retained.retained_result_payload == result

    exhausted_request = dict(call_request)
    exhausted_request["call_id"] = "call-2"
    exhausted = await _reserve_model_call(repository, binding, exhausted_request)
    restarted = AsyncGovernedAgentRepository(db_path)

    assert exhausted.status == "exhausted"
    assert await restarted.list_call_records(invocation_id=binding.invocation_id) == (record,)


def _result_without_model_usage() -> dict[str, Any]:
    result = agent_iteration_result()
    result["model_receipts"] = []
    result["usage"] = {
        **result["usage"],
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "charged_input_tokens": 0,
        "charged_output_tokens": 0,
    }
    return result


def _continuation_inputs() -> GovernedAgentContinuationInputs:
    return GovernedAgentContinuationInputs(
        valid_recorded_result=True,
        effect_approval_required=False,
        unresolved_effect_boundary=False,
        policy_violation=False,
        quarantine_required=False,
        accepted_cancel=False,
        accepted_terminal_stop=False,
        verified_objective_satisfied=False,
        verification_evidence_sufficient=False,
        deadline_expired=False,
        lease_expired=False,
        capability_budget_exhausted=False,
        effect_budget_exhausted=False,
        iteration_budget_exhausted=False,
        model_budget_exhausted=False,
        token_budget_exhausted=False,
        output_budget_exhausted=False,
        artifact_budget_exhausted=False,
        unrecoverable_execution_failure=False,
        repeated_state_threshold_hit=False,
        no_progress_threshold_hit=False,
        extension_recommendation="continue",
    )


async def _publish_and_assert_continuation(repository, binding, outcome) -> None:
    inputs = _continuation_inputs()
    decision = decide_governed_agent_continuation(inputs)
    publications = [
        await repository.publish_continuation_decision(
            binding=binding,
            accepted_result_digest=str(outcome.result_digest),
            decision_inputs=inputs.to_payload(),
            decision_payload=decision.to_payload(),
        )
        for _ in range(2)
    ]
    snapshot = await repository.get_iteration_snapshot(invocation_id=binding.invocation_id)
    assert [item.status for item in publications] == ["accepted", "idempotent"]
    assert snapshot is not None and snapshot.state == "decided"
    assert snapshot.decision_payload == decision.to_payload()
    assert snapshot.decision_inputs is not None
    replayed = decide_governed_agent_continuation(
        GovernedAgentContinuationInputs(**snapshot.decision_inputs)
    )
    assert replayed == decision


async def _reserve_model_call(repository, binding, request: dict[str, Any]):
    return await repository.reserve_call(
        binding=binding,
        operation="model.call.v1",
        call_id=str(request["call_id"]),
        role=str(request["role"]),
        request_digest=prefixed_digest(request),
        reserved_input_tokens=int(request["max_input_tokens"]),
        reserved_output_tokens=int(request["max_output_tokens"]),
    )
