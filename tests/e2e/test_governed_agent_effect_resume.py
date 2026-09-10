# Layer: end-to-end

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_effect_records import aggregate_effect_checkpoint
from orket.application.services.governed_agent_effect_resume_service import GovernedAgentEffectResumeService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_fixture import SecondIterationDeterministicVerifier
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.governed_agent_ports import GovernedAgentAuthorityStaleError
from orket.core.domain import CheckpointReobservationClass, RunState
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk import AgentEffectProposal, AgentIterationRequest, AgentIterationResult
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    agent_request,
    agent_workload_record,
    resolved_profiles,
)

pytestmark = [pytest.mark.end_to_end, pytest.mark.integration]


@pytest.mark.asyncio
async def test_effect_approval_pauses_then_resumes_with_verified_receipts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    await AsyncFileTools(tmp_path).write_file("inputs/tickets.json", {"source": "fixture"})
    request_payload = _effect_request()
    db_path = tmp_path / "agent-effect-loop.sqlite3"
    execution = AsyncControlPlaneExecutionRepository(db_path)
    iterations = AsyncGovernedAgentRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    loop = _loop(execution, iterations, records)
    now = datetime.now(UTC)

    first = await loop.run_bounded(
        initial_request_payload=request_payload,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=((now + timedelta(seconds=1)).isoformat(), (now + timedelta(seconds=2)).isoformat()),
        next_lease_expiries_utc=((now + timedelta(seconds=7)).isoformat(),),
    )

    assert first.run.lifecycle_state is RunState.OPERATOR_BLOCKED
    assert first.decisions[0].rule == "effect_approval_required"
    snapshot = (await iterations.list_iteration_snapshots(run_id="run-1"))[0]
    assert snapshot.result_payload is not None
    request = AgentIterationRequest.from_wire(snapshot.request_payload)
    proposals = [AgentEffectProposal.from_wire(item) for item in snapshot.result_payload["effect_proposals"]]
    result = AgentIterationResult.from_wire(snapshot.result_payload)
    publication = ControlPlanePublicationService(repository=records)
    effects = GovernedAgentEffectService(
        execution_repository=execution,
        publication=publication,
        pending_gates=AsyncPendingGateRepository(db_path),
        file_executor=GovernedAgentFileEffectExecutor(tmp_path),
    )
    receipts = []
    for proposal in proposals:
        prepared = await effects.prepare(
            request=request,
            proposal=proposal,
            created_at=(now + timedelta(seconds=3)).isoformat(),
        )
        if prepared.approval_id is None:
            receipts.append(prepared.receipt)
            continue
        resolved = await effects.resolve_write(
            approval_id=prepared.approval_id,
            decision="approved",
            actor_ref="operator:test",
            timestamp=(now + timedelta(seconds=4)).isoformat(),
        )
        receipts.append(resolved.receipt)
    journals = tuple(await records.list_effect_journal_entries(run_id="run-1"))
    checkpoint = aggregate_effect_checkpoint(
        request,
        result,
        journals,
        (now + timedelta(seconds=5)).isoformat(),
    )
    acceptance = await publication.accept_checkpoint(
        acceptance_id="agent-effects-checkpoint-acceptance:agent-invocation:run-1:00000001",
        checkpoint=checkpoint,
        supervisor_authority_ref="governed-agent-effect-control-service:v1",
        decision_timestamp=(now + timedelta(seconds=5)).isoformat(),
        required_reobservation_class=CheckpointReobservationClass.NONE,
        integrity_verification_ref=checkpoint.integrity_verification_ref,
        journal_entries=journals,
        dependent_effect_entry_refs=tuple(entry.journal_entry_id for entry in journals),
    )
    resume = GovernedAgentEffectResumeService(
        execution_repository=execution,
        iteration_repository=iterations,
        publication=publication,
    )
    resumed = await resume.prepare_resume(
        run_id="run-1",
        effect_receipts=tuple(receipts),
        accepted_checkpoint_ref=acceptance.checkpoint_id,
        next_lease_expires_at_utc=(now + timedelta(seconds=7)).isoformat(),
        actor_ref="operator:test",
        timestamp=(now + timedelta(seconds=5)).isoformat(),
    )
    blocked = await execution.get_run_record(run_id="run-1")
    assert blocked is not None and blocked.lifecycle_state is RunState.OPERATOR_BLOCKED
    tampered_payload = resumed.request.to_wire()
    tampered_payload["recovery_ref"] = "recovery:tampered"
    with pytest.raises(ValueError, match="E_AGENT_EFFECT_RESUME_AUTHORIZATION_MISSING"):
        await resume.activate_resume(
            request=AgentIterationRequest.from_wire(tampered_payload),
            authority_guard=_AlwaysActiveGuard(),
        )
    with pytest.raises(GovernedAgentAuthorityStaleError, match="E_AGENT_WAKE_CLAIM_STALE"):
        await resume.activate_resume(request=resumed.request, authority_guard=_StaleGuard())
    still_blocked = await execution.get_run_record(run_id="run-1")
    assert still_blocked is not None and still_blocked.lifecycle_state is RunState.OPERATOR_BLOCKED
    await resume.activate_resume(request=resumed.request, authority_guard=_AlwaysActiveGuard())

    second = await loop.run_bounded(
        initial_request_payload=resumed.request.to_wire(),
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=((now + timedelta(seconds=6)).isoformat(),),
        next_lease_expiries_utc=(),
    )

    assert second.run.lifecycle_state is RunState.COMPLETED
    second_snapshot = max(
        await iterations.list_iteration_snapshots(run_id="run-1"),
        key=lambda item: item.binding.iteration_ordinal,
    )
    assert [receipt["state"] for receipt in second_snapshot.request_payload["effect_receipts"]] == [
        "observed",
        "observed",
    ]
    assert second_snapshot.request_payload["accepted_checkpoint_ref"] == acceptance.checkpoint_id
    assert tmp_path.joinpath("reports", "ticket-report.json").is_file()


def _loop(execution, iterations, records) -> GovernedAgentLoopService:
    provider = DeterministicModelProvider()
    broker = GovernedAgentHostBroker(
        iteration_repository=iterations,
        call_repository=iterations,
        model_provider=provider,
        model_profiles=resolved_profiles(),
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent",
        allowed_stdlib_modules=("json",),
        broker=broker,
        handshake_timeout_seconds=2,
    )
    return GovernedAgentLoopService(
        execution_repository=execution,
        iteration_repository=iterations,
        truth_repository=records,
        invoker=invoker,
        verifier=SecondIterationDeterministicVerifier(),
    )


class _AlwaysActiveGuard:
    async def ensure_active(self) -> None:
        return None


class _StaleGuard:
    async def ensure_active(self) -> None:
        raise GovernedAgentAuthorityStaleError("E_AGENT_WAKE_CLAIM_STALE")


def _effect_request() -> dict:
    request = agent_request()
    request["namespace_scope"] = ["issue:issue-1"]
    request["admitted_capabilities"] = ["agent.iteration.v1", "read_file", "write_file"]
    request["extension_config"] = {
        "effect_demo": {
            "enabled": True,
            "namespace": "issue:issue-1",
            "read_path": "inputs/tickets.json",
            "write_path": "reports/ticket-report.json",
        }
    }
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request[scope]
        budget["per_capability_effects"] = [
            {"capability": "read_file", "count": 1},
            {"capability": "write_file", "count": 1},
        ]
        budget["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in budget.items() if key != "snapshot_digest"}
        )
    return request
