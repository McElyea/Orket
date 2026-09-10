# Layer: integration

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.application.services.governed_agent_ports import GovernedAgentAuthorityStaleError
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, ResidualUncertaintyClassification, RunState
from orket_extension_sdk import AgentEffectProposal, AgentIterationRequest, canonical_digest_sha256
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import agent_request

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_competing_approval_resolutions_admit_only_one_real_write(tmp_path, monkeypatch):
    """Layer: integration. Concurrent readers compete through the durable pending-status CAS."""
    request, service, _, records = await _setup(tmp_path)
    proposal = _proposal(request, "write-race", "write_file", "reports/race.json", {"open": 2})
    prepared = await service.prepare(request=request, proposal=proposal, created_at="2026-09-09T12:00:00Z")
    arrived, count, writes = asyncio.Event(), 0, []
    real_resolve = AsyncPendingGateRepository.resolve_request
    real_write = GovernedAgentFileEffectExecutor.write

    async def simultaneous_resolve(self, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            arrived.set()
        await asyncio.wait_for(arrived.wait(), 5)
        return await real_resolve(self, **kwargs)

    async def counted_write(self, **kwargs):
        writes.append(kwargs)
        return await real_write(self, **kwargs)

    monkeypatch.setattr(AsyncPendingGateRepository, "resolve_request", simultaneous_resolve)
    monkeypatch.setattr(GovernedAgentFileEffectExecutor, "write", counted_write)
    results = await asyncio.gather(*(service.resolve_write(approval_id=prepared.approval_id,
        decision="approved", actor_ref=f"operator:{actor}", timestamp="2026-09-09T12:00:01Z")
        for actor in ("first", "second")), return_exceptions=True)
    assert sum(isinstance(result, ValueError) for result in results) == 1
    assert any(str(result) == "E_AGENT_EFFECT_APPROVAL_ALREADY_RESOLVED" for result in results)
    assert len(writes) == 1
    assert len(await records.list_effect_journal_entries(run_id=request.identity.run_id)) == 1
    assert await AsyncFileTools(tmp_path).read_file("reports/race.json") == '{\n  "open": 2\n}'


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
    inspector = GovernedAgentInspectionService(
        execution_repository=execution,
        iteration_repository=AsyncGovernedAgentRepository(tmp_path / "agent-effects.sqlite3"),
        call_repository=AsyncGovernedAgentRepository(tmp_path / "agent-effects.sqlite3"),
        truth_repository=records,
        record_repository=records,
        pending_gate_repository=AsyncPendingGateRepository(tmp_path / "agent-effects.sqlite3"),
    )
    inspection = await inspector.inspect(run_id=request.identity.run_id)
    assert inspection is not None
    assert len(inspection["effects"]) == 2
    assert [item["status"] for item in inspection["approvals"]] == ["approved"]
    assert len(inspection["checkpoints"]) == 2
    assert len(inspection["operator_actions"]) == 2
    assert inspection["operator_summary"]["effect_count"] == 2


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


@pytest.mark.asyncio
async def test_stale_wake_cannot_publish_observed_effect_after_external_read(tmp_path: Path) -> None:
    """Layer: integration. The wake fence is rechecked after observation and before journal publication."""
    request, service, _, records = await _setup(tmp_path)
    await AsyncFileTools(tmp_path).write_file("inputs/tickets.json", {"ready": True})
    proposal = _proposal(request, "read-stale", "read_file", "inputs/tickets.json")
    guard = _ExpiringGuard(allowed_checks=2)

    with pytest.raises(GovernedAgentAuthorityStaleError, match="E_AGENT_WAKE_CLAIM_STALE"):
        await service.prepare(
            request=request,
            proposal=proposal,
            created_at="2026-09-07T18:30:00Z",
            authority_guard=guard,
        )

    assert await records.list_effect_journal_entries(run_id=request.identity.run_id) == []


@pytest.mark.asyncio
async def test_unobserved_approved_write_moves_run_to_recovery_without_claiming_success(tmp_path: Path) -> None:
    """Layer: integration. An unverified write remains uncertain and blocks all continuation."""
    request, service, execution, records = await _setup(tmp_path)
    proposal = _proposal(
        request,
        "write-uncertain",
        "write_file",
        "../outside.json",
        {"must_not": "escape"},
    )
    pending = await service.prepare(
        request=request,
        proposal=proposal,
        created_at="2026-09-07T18:40:00Z",
    )
    assert pending.approval_id is not None

    resolution = await service.resolve_write(
        approval_id=pending.approval_id,
        decision="approved",
        actor_ref="operator:test",
        timestamp="2026-09-07T18:40:01Z",
    )

    run = await execution.get_run_record(run_id=request.identity.run_id)
    entries = await records.list_effect_journal_entries(run_id=request.identity.run_id)
    assert resolution.receipt.state == "uncertain"
    assert resolution.accepted_checkpoint_ref is None
    assert run is not None and run.lifecycle_state is RunState.RECOVERY_PENDING
    assert entries[-1].uncertainty_classification is ResidualUncertaintyClassification.UNRESOLVED
    assert not tmp_path.parent.joinpath("outside.json").exists()


@pytest.mark.asyncio
async def test_failed_read_observation_is_journaled_as_recovery_pending(tmp_path: Path) -> None:
    """Layer: integration. A failed read is durable uncertainty rather than a missing effect."""
    request, service, execution, records = await _setup(tmp_path)
    proposal = _proposal(request, "read-missing", "read_file", "inputs/missing.json")

    preparation = await service.prepare(
        request=request,
        proposal=proposal,
        created_at="2026-09-07T18:50:00Z",
    )

    run = await execution.get_run_record(run_id=request.identity.run_id)
    entries = await records.list_effect_journal_entries(run_id=request.identity.run_id)
    assert preparation.receipt.state == "uncertain"
    assert run is not None and run.lifecycle_state is RunState.RECOVERY_PENDING
    assert entries[-1].effect_id == "agent-effect:read-missing"
    assert entries[-1].uncertainty_classification is ResidualUncertaintyClassification.UNRESOLVED


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


class _ExpiringGuard:
    def __init__(self, *, allowed_checks: int) -> None:
        self._remaining = allowed_checks

    async def ensure_active(self) -> None:
        if self._remaining <= 0:
            raise GovernedAgentAuthorityStaleError("E_AGENT_WAKE_CLAIM_STALE")
        self._remaining -= 1
