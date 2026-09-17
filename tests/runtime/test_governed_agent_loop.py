# Layer: integration and end-to-end

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_inspection_service import (
    GovernedAgentInspectionService,
)
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.governed_agent_memory_service import GovernedAgentObjectiveMemory
from orket.core.domain import AttemptState, RunState
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    SecondIterationVerifier,
    UnexpectedBroker,
    agent_request,
    agent_workload_record,
    binding_for,
    prepare_authority,
    resolved_profiles,
    staged_agent_request,
    ticket_continuation_inputs,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.end_to_end
@pytest.mark.parametrize("staged,memory", [(False, False), (True, False), (True, True)])
# Layer: integration
async def test_two_iteration_governor_replays_decisions_and_publishes_verified_truth(
    tmp_path: Path,
    monkeypatch,
    staged: bool,
    memory: bool,
) -> None:
    """Layer: end-to-end. Exercises two real child invocations through durable host authority."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    db_path = tmp_path / "agent-loop.sqlite3"
    request = staged_agent_request() if staged else agent_request()
    context_plan = ticket_continuation_inputs() if staged else {}
    if memory:
        request["admitted_capabilities"].append("memory.query")
        request["extension_config"] = {"objective_memory": True}
    repository = AsyncGovernedAgentRepository(db_path)
    provider = DeterministicModelProvider()
    broker = GovernedAgentHostBroker(
        iteration_repository=repository,
        call_repository=repository,
        model_provider=provider,
        model_profiles=resolved_profiles(),
        memory_provider=GovernedAgentObjectiveMemory(repository),
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent",
        allowed_stdlib_modules=("json",),
        broker=broker,
        handshake_timeout_seconds=2,
    )
    service = GovernedAgentLoopService(
        execution_repository=AsyncControlPlaneExecutionRepository(db_path),
        iteration_repository=repository,
        transactions=SQLiteControlPlaneTransactions(db_path),
        invoker=invoker,
        verifier=SecondIterationVerifier(),
    )
    now = datetime.now(UTC)

    execution = await service.run_bounded(
        initial_request_payload=request,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=((now + timedelta(seconds=1)).isoformat(), (now + timedelta(seconds=2)).isoformat()),
        next_lease_expiries_utc=((now + timedelta(seconds=7)).isoformat(),),
        continuation_inputs_payload=context_plan,
    )

    await _assert_completed_two_iteration_run(
        execution=execution,
        provider=provider,
        repository=repository,
        control_plane=AsyncControlPlaneExecutionRepository(db_path),
        service=service,
        request=request,
        now=now,
        db_path=db_path,
        context_plan=context_plan,
        memory=memory,
    )


async def _assert_completed_two_iteration_run(
    *,
    execution,
    provider,
    repository,
    control_plane,
    service,
    request,
    now,
    db_path,
    context_plan,
    memory,
) -> None:
    assert execution.run.lifecycle_state is RunState.COMPLETED
    assert execution.attempt.attempt_state is AttemptState.COMPLETED
    assert [decision.disposition for decision in execution.decisions] == ["continue", "complete"]
    assert provider.roles == ["planner", "actor", "critic"] * 2
    assert execution.final_truth is not None
    assert execution.final_truth.authoritative_result_ref == "agent-result:agent-invocation:run-1:00000002"
    steps = await control_plane.list_step_records(attempt_id="attempt-1")
    assert len(steps) == 2
    second = await repository.get_iteration_snapshot(invocation_id="agent-invocation:run-1:00000002")
    assert second is not None
    assert second.decision_inputs is not None
    assert second.decision_payload is not None
    assert second.result_payload is not None
    assert second.request_payload["prior_verified_output_refs"] == ["agent-result:invocation-1"]
    if context_plan:
        first = await repository.get_iteration_snapshot(invocation_id="invocation-1")
        assert first.request_payload["authoritative_context_refs"] == ["artifact:ticket-batch-a"]
        assert not any(item["reference"] == "artifact:ticket-batch-b"
                       for item in first.request_payload["materialized_inputs"])
        assert second.request_payload["authoritative_context_refs"] == ["artifact:ticket-batch-b"]
        assert json.loads(first.result_payload["advisory_proposal"])["counts"] == {"closed": 1, "open": 2}
    proposal = json.loads(second.result_payload["advisory_proposal"])
    assert proposal["counts"] == {"blocked": 1, "closed": 2, "open": 2}
    assert proposal["source_refs"] == ["artifact:ticket-batch-a", "artifact:ticket-batch-b"]
    replayed = decide_governed_agent_continuation(
        GovernedAgentContinuationInputs(**second.decision_inputs)
    )
    assert replayed.to_payload() == second.decision_payload
    duplicate = await service.run_bounded(
        initial_request_payload=request,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=(now + timedelta(seconds=3)).isoformat(),
        decision_timestamps_utc=((now + timedelta(seconds=4)).isoformat(), (now + timedelta(seconds=5)).isoformat()),
        next_lease_expiries_utc=((now + timedelta(seconds=7)).isoformat(),),
        continuation_inputs_payload=context_plan,
    )
    assert duplicate.final_truth == execution.final_truth
    assert duplicate.invocation_ids == ()
    assert provider.roles == ["planner", "actor", "critic"] * 2
    inspector = GovernedAgentInspectionService(
        replay_repository=GovernedAgentReplayStore(db_path),
        iteration_repository=repository,
        call_repository=repository,
    )
    inspection = await inspector.inspect(run_id="run-1")
    replay = await inspector.replay(run_id="run-1")
    assert inspection is not None
    assert len(inspection["iterations"]) == 2
    assert len(inspection["iterations"][0]["model_calls"]) == (4 if memory else 3)
    if memory:
        first_calls = await repository.list_call_records(invocation_id="invocation-1")
        second_calls = await repository.list_call_records(invocation_id="agent-invocation:run-1:00000002")
        first_memory = next(item for item in first_calls if item.operation == "memory.query.v1")
        second_memory = next(item for item in second_calls if item.operation == "memory.query.v1")
        assert first_memory.result_payload["entries"] == []
        assert len(second_memory.result_payload["entries"]) == 1
        assert second_memory.result_payload["entries"][0]["content"]["counts"] == {"closed": 1, "open": 2}
        assert second_memory.result_payload["entries"][0]["provenance_refs"] == [
            "agent-result:invocation-1", "agent-decision:invocation-1"]
    assert replay is not None
    assert replay["status"] == "matched"
    assert [item["disposition"] for item in replay["decisions"]] == ["continue", "complete"]


@pytest.mark.asyncio
# Layer: integration
async def test_restart_after_dispatch_blocks_without_redispatch(tmp_path: Path) -> None:
    """Layer: integration. A prepared dispatch without a result becomes explicit recovery state."""
    db_path = tmp_path / "restart.sqlite3"
    request = agent_request()
    binding = binding_for(request)
    repository = await prepare_authority(db_path, request, binding)
    service = GovernedAgentLoopService(
        execution_repository=AsyncControlPlaneExecutionRepository(db_path),
        iteration_repository=repository,
        transactions=SQLiteControlPlaneTransactions(db_path),
        invoker=UnexpectedBroker(),  # type: ignore[arg-type]
        verifier=SecondIterationVerifier(),
    )
    now = datetime.now(UTC)

    execution = await service.run_bounded(
        initial_request_payload=request,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=((now + timedelta(seconds=1)).isoformat(), (now + timedelta(seconds=2)).isoformat()),
        next_lease_expiries_utc=((now + timedelta(seconds=7)).isoformat(),),
    )

    assert execution.run.lifecycle_state is RunState.RECOVERY_PENDING
    assert execution.normalized_reason == "restart_after_dispatch_requires_recovery"
    snapshot = await repository.get_iteration_snapshot(invocation_id=binding.invocation_id)
    assert snapshot is not None
    assert snapshot.state == "interrupted"
    assert snapshot.uncertainty is True


@pytest.mark.asyncio
# Layer: integration
async def test_real_child_crash_becomes_recovery_pending_uncertainty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. A child disconnect is normalized and durably blocks redispatch."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    extension_root = tmp_path / "crash-agent"
    extension_root.mkdir()
    extension_root.joinpath("crash_agent.py").write_text(
        "class CrashAgent:\n"
        "    async def run(self, context):\n"
        "        raise RuntimeError('fixture child crash')\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "crash.sqlite3"
    request = agent_request()
    repository = AsyncGovernedAgentRepository(db_path)
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=extension_root,
        entrypoint="crash_agent:CrashAgent",
        allowed_stdlib_modules=("json",),
        broker=UnexpectedBroker(),  # type: ignore[arg-type]
        handshake_timeout_seconds=2,
    )
    service = GovernedAgentLoopService(
        execution_repository=AsyncControlPlaneExecutionRepository(db_path),
        iteration_repository=repository,
        transactions=SQLiteControlPlaneTransactions(db_path),
        invoker=invoker,
        verifier=SecondIterationVerifier(),
    )
    now = datetime.now(UTC)

    execution = await service.run_bounded(
        initial_request_payload=request,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=(
            (now + timedelta(seconds=1)).isoformat(),
            (now + timedelta(seconds=2)).isoformat(),
        ),
        next_lease_expiries_utc=((now + timedelta(seconds=7)).isoformat(),),
    )

    assert execution.run.lifecycle_state is RunState.RECOVERY_PENDING
    assert execution.normalized_reason == "E_AGENT_CHILD_DISCONNECTED"
    snapshot = await repository.get_iteration_snapshot(invocation_id="invocation-1")
    assert snapshot is not None
    assert snapshot.state == "interrupted"
    assert snapshot.uncertainty is True
    assert "fixture child crash" in invoker.last_diagnostic_tail
