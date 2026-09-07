# Layer: integration

from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, RunState
from orket_extension_sdk import AgentEffectProposal, AgentIterationRequest, canonical_digest_sha256
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_observe_and_approved_write_follow_existing_effect_authorities(tmp_path: Path) -> None:
    request, service, execution, records = await _setup(tmp_path)
    await AsyncFileTools(tmp_path).write_file("inputs/tickets.json", {"ready": True})
    read = _proposal(request, "read-1", "read_file", "inputs/tickets.json")
    write = _proposal(
        request,
        "write-1",
        "write_file",
        "reports/ticket-report.json",
        {"counts": {"blocked": 1, "closed": 2, "open": 2}},
    )

    observed = await service.prepare(request=request, proposal=read, created_at="2026-09-07T18:00:00Z")
    pending = await service.prepare(request=request, proposal=write, created_at="2026-09-07T18:00:01Z")

    assert observed.receipt.state == "observed"
    assert pending.receipt.state == "proposed"
    assert pending.approval_id is not None
    assert not tmp_path.joinpath("reports", "ticket-report.json").exists()
    run = await execution.get_run_record(run_id=request.identity.run_id)
    assert run is not None and run.namespace_scope == "issue:issue-1"

    resolved = await service.resolve_write(
        approval_id=pending.approval_id,
        decision="approved",
        actor_ref="operator:test",
        timestamp="2026-09-07T18:00:02Z",
    )

    assert resolved.receipt.state == "observed"
    assert resolved.effect_journal_ref is not None
    assert resolved.accepted_checkpoint_ref == "agent-post-effect-checkpoint:write-1"
    assert await AsyncFileTools(tmp_path).read_file("reports/ticket-report.json") == (
        '{\n  "counts": {\n    "blocked": 1,\n    "closed": 2,\n    "open": 2\n  }\n}'
    )
    entries = await records.list_effect_journal_entries(run_id=request.identity.run_id)
    assert [entry.effect_id for entry in entries] == ["agent-effect:read-1", "agent-effect:write-1"]
    repeated = await service.resolve_write(
        approval_id=pending.approval_id,
        decision="approved",
        actor_ref="operator:test",
        timestamp="2026-09-07T18:00:02Z",
    )
    assert repeated.effect_journal_ref == resolved.effect_journal_ref
    assert len(await records.list_effect_journal_entries(run_id=request.identity.run_id)) == 2


@pytest.mark.asyncio
async def test_denied_write_never_mutates_and_rejects_resume_checkpoint(tmp_path: Path) -> None:
    request, service, execution, records = await _setup(tmp_path)
    proposal = _proposal(request, "write-denied", "write_file", "reports/denied.json", {"denied": False})
    pending = await service.prepare(
        request=request,
        proposal=proposal,
        created_at="2026-09-07T18:10:00Z",
    )
    assert pending.approval_id is not None

    denied = await service.resolve_write(
        approval_id=pending.approval_id,
        decision="denied",
        actor_ref="operator:test",
        timestamp="2026-09-07T18:10:01Z",
    )

    assert denied.receipt.state == "denied"
    assert not tmp_path.joinpath("reports", "denied.json").exists()
    assert await records.list_effect_journal_entries(run_id=request.identity.run_id) == []
    acceptance = await records.get_checkpoint_acceptance(
        checkpoint_id="agent-pre-effect-checkpoint:write-denied"
    )
    assert acceptance is not None
    assert acceptance.rejection_reasons == ["operator_denied_effect"]
    run = await execution.get_run_record(run_id=request.identity.run_id)
    assert run is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id == "agent-effect-denial-final-truth:run-1"


@pytest.mark.asyncio
async def test_restart_after_write_reconciles_observed_content_without_duplicate_effect(tmp_path: Path) -> None:
    request, service, _, records = await _setup(tmp_path)
    content = {"counts": {"open": 2}}
    proposal = _proposal(request, "write-reconcile", "write_file", "reports/reconciled.json", content)
    pending = await service.prepare(
        request=request,
        proposal=proposal,
        created_at="2026-09-07T18:20:00Z",
    )
    assert pending.approval_id is not None
    await AsyncFileTools(tmp_path).write_file("reports/reconciled.json", content)

    resolved = await service.resolve_write(
        approval_id=pending.approval_id,
        decision="approved",
        actor_ref="operator:test",
        timestamp="2026-09-07T18:20:01Z",
    )

    assert resolved.receipt.state == "reconciled"
    entries = await records.list_effect_journal_entries(run_id=request.identity.run_id)
    assert len(entries) == 1
    assert entries[0].effect_id == "agent-effect:write-reconcile"


async def _setup(tmp_path: Path):
    db_path = tmp_path / "agent-effects.sqlite3"
    execution = AsyncControlPlaneExecutionRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    request_payload = agent_request()
    request_payload["namespace_scope"] = ["issue:issue-1"]
    request_payload["admitted_capabilities"] = ["agent.iteration.v1", "read_file", "write_file"]
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request_payload[scope]
        budget["per_capability_effects"] = [
            {"capability": "read_file", "count": 1},
            {"capability": "write_file", "count": 1},
        ]
        budget["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in budget.items() if key != "snapshot_digest"}
        )
    request = AgentIterationRequest.from_wire(request_payload)
    await execution.save_run_record(
        record=RunRecord(
            run_id=request.identity.run_id,
            workload_id="governed-agent-loop",
            workload_version="0.1.0",
            policy_snapshot_id=request.policy_ref,
            policy_digest=request.policy_digest,
            configuration_snapshot_id="agent-config:run-1",
            configuration_digest="sha256:" + "c" * 64,
            creation_timestamp="2026-09-07T17:59:00Z",
            admission_decision_receipt_ref="agent-admission:test",
            namespace_scope="issue:issue-1",
            lifecycle_state=RunState.OPERATOR_BLOCKED,
            current_attempt_id=request.identity.attempt_id,
        )
    )
    await execution.save_attempt_record(
        record=AttemptRecord(
            attempt_id=request.identity.attempt_id,
            run_id=request.identity.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="agent-state:initial",
            start_timestamp="2026-09-07T17:59:00Z",
        )
    )
    await execution.save_step_record(
        record=StepRecord(
            step_id=request.identity.step_id,
            attempt_id=request.identity.attempt_id,
            step_kind="governed_agent_iteration",
            namespace_scope="issue:issue-1",
            input_ref="sha256:" + "d" * 64,
            observed_result_classification="proposal_recorded",
            closure_classification="step_open",
        )
    )
    service = GovernedAgentEffectService(
        execution_repository=execution,
        publication=ControlPlanePublicationService(repository=records),
        pending_gates=AsyncPendingGateRepository(db_path),
        file_executor=GovernedAgentFileEffectExecutor(tmp_path),
    )
    return request, service, execution, records


def _proposal(
    request: AgentIterationRequest,
    proposal_id: str,
    capability: str,
    path: str,
    content=None,
) -> AgentEffectProposal:
    arguments = {"path": path}
    if content is not None:
        arguments["content"] = content
    return AgentEffectProposal(
        identity=request.identity,
        proposal_id=proposal_id,
        capability=capability,
        intended_target=path,
        namespace="issue:issue-1",
        arguments=arguments,
        arguments_ref=None,
        arguments_digest="sha256:" + canonical_digest_sha256(arguments),
        idempotency_key=f"agent-effect:{proposal_id}",
        evidence_refs=("agent-result:invocation-1",),
    )
