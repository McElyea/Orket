# Layer: end-to-end

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psutil
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_effect_records import aggregate_effect_checkpoint
from orket.application.services.governed_agent_effect_resume_service import (
    GovernedAgentEffectResumeService,
    GovernedAgentResumePreparation,
)
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_fixture import SecondIterationDeterministicVerifier
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.tool_gate_service import ToolGate
from orket.core.contracts import CheckpointAcceptanceRecord
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityStaleError
from orket.core.domain import CheckpointReobservationClass, RunState
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk import AgentEffectProposal, AgentIterationRequest, AgentIterationResult
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    agent_request,
    agent_workload_record,
    resolved_profiles,
)

pytestmark = [pytest.mark.end_to_end, pytest.mark.integration, pytest.mark.usefixtures("elapsed_agent_clock")]


@pytest.fixture
async def native_children(monkeypatch):
    """Every case retains and checks its actual subprocess handles."""
    original = GovernedAgentSubprocessInvoker._start_child
    processes = []

    async def start(owner):
        process = await original(owner)
        processes.append(process)
        return process

    monkeypatch.setattr(GovernedAgentSubprocessInvoker, "_start_child", start)
    try:
        yield processes
    finally:
        assert processes
        assert all(process.returncode is not None for process in processes)


@pytest.fixture(params=[(0, None), (2.25, None), (2.25, 2)],
                ids=["normal", "delayed-startup", "handshake-expiry"])
async def startup_case(request, monkeypatch, native_children):
    """Retain real children through a controlled pause before their ready frame."""
    delay, handshake_timeout = request.param
    original = GovernedAgentSubprocessInvoker._start_child
    releases = []

    async def start(owner):
        process = await original(owner)
        if len(native_children) == 2 and delay:
            await asyncio.to_thread(psutil.Process(process.pid).suspend)
            releases.append(asyncio.create_task(_resume_child(process, delay)))
        return process

    monkeypatch.setattr(GovernedAgentSubprocessInvoker, "_start_child", start)
    try:
        yield handshake_timeout
    finally:
        await asyncio.gather(*releases)
        assert len(native_children) == 2


async def _resume_child(process, delay):
    await asyncio.sleep(delay)
    try:
        await asyncio.to_thread(psutil.Process(process.pid).resume)
    except psutil.NoSuchProcess:
        # Native exit may precede asyncio's process-exit callback on Windows.
        await asyncio.wait_for(process.wait(), timeout=5)


@pytest.mark.asyncio
# Layer: end-to-end
async def test_effect_approval_pauses_then_resumes_with_verified_receipts(
    tmp_path: Path, monkeypatch, startup_case,
) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    case = await _prepare_resume_case(tmp_path, handshake_timeout=startup_case)
    await case.resume.activate_resume(request=case.resumed.request, authority_guard=_AlwaysActiveGuard())
    second = await _run_loop(
        case.loop, case.resumed.request.to_wire(), case.now,
        decisions=((case.now + timedelta(seconds=6)).isoformat(),), lease_expiries=(),
    )
    if startup_case is None:
        assert second.run.lifecycle_state is RunState.COMPLETED
    else:
        assert second.run.lifecycle_state is RunState.RECOVERY_PENDING
        assert second.normalized_reason == "E_SDK_AGENT_FRAME_READ_TIMEOUT"
        assert second.final_truth is None
    snapshots = await case.iterations.list_iteration_snapshots(run_id="run-1")
    second_snapshot = max(snapshots, key=lambda item: item.binding.iteration_ordinal)
    assert [receipt["state"] for receipt in second_snapshot.request_payload["effect_receipts"]] == [
        "observed", "observed",
    ]
    assert second_snapshot.request_payload["accepted_checkpoint_ref"] == case.acceptance.checkpoint_id
    assert second_snapshot.request_payload["deadline_utc"] == snapshots[0].request_payload["deadline_utc"]
    assert tmp_path.joinpath("reports", "ticket-report.json").is_file()


@pytest.mark.asyncio
# Layer: end-to-end
async def test_effect_resume_rejections_preserve_blocked_authority(tmp_path, monkeypatch, native_children):
    """Rejection checks have their own real pause, outside the successful resume's deadline."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    case = await _prepare_resume_case(tmp_path)
    blocked = await case.execution.get_run_record(run_id="run-1")
    assert blocked is not None and blocked.lifecycle_state is RunState.OPERATOR_BLOCKED
    tampered_payload = case.resumed.request.to_wire()
    tampered_payload["recovery_ref"] = "recovery:tampered"
    with pytest.raises(ValueError, match="E_AGENT_EFFECT_RESUME_AUTHORIZATION_MISSING"):
        await case.resume.activate_resume(
            request=AgentIterationRequest.from_wire(tampered_payload),
            authority_guard=_AlwaysActiveGuard(),
        )
    assert await case.execution.get_run_record(run_id="run-1") == blocked
    with pytest.raises(GovernedAgentAuthorityStaleError, match="E_AGENT_WAKE_CLAIM_STALE"):
        await case.resume.activate_resume(request=case.resumed.request, authority_guard=_StaleGuard())
    assert await case.execution.get_run_record(run_id="run-1") == blocked
    await case.resume.activate_resume(request=case.resumed.request, authority_guard=_AlwaysActiveGuard())
    assert (await case.execution.get_run_record(run_id="run-1")).lifecycle_state is RunState.EXECUTING
    assert len(await case.iterations.list_iteration_snapshots(run_id="run-1")) == 1
    assert len(native_children) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["first", "resume"])
# Layer: end-to-end
async def test_wall_clock_expiry_retains_native_uncertainty(
    tmp_path, monkeypatch, native_children, elapsed_agent_clock, phase,
):
    """An explicit UTC jump expires the unchanged deadline and cannot invent success."""
    from tests.integration.test_governed_agent_acceptance_failures import _run

    original = GovernedAgentSubprocessInvoker._start_child
    target = 1 if phase == "first" else 2

    async def start(owner):
        process = await original(owner)
        if len(native_children) == target:
            await asyncio.to_thread(psutil.Process(process.pid).suspend)
            elapsed_agent_clock.jump(9)
        return process

    monkeypatch.setattr(GovernedAgentSubprocessInvoker, "_start_child", start)
    if phase == "first":
        source = await asyncio.to_thread((TEMPLATE_ROOT / "governed_agent.py").read_text, encoding="utf-8")
        payload = agent_request()
        result, iterations = await _run(tmp_path, source, payload)
    else:
        case = await _prepare_resume_case(tmp_path)
        payload = case.resumed.request.to_wire()
        await case.resume.activate_resume(request=case.resumed.request, authority_guard=_AlwaysActiveGuard())
        result = await _run_loop(case.loop, payload, case.now,
                                 decisions=((case.now + timedelta(seconds=6)).isoformat(),), lease_expiries=())
        iterations = case.iterations
    assert elapsed_agent_clock.elapsed_seconds < 8
    assert result.run.lifecycle_state is RunState.RECOVERY_PENDING
    assert result.normalized_reason == "E_SDK_AGENT_FRAME_READ_TIMEOUT"
    assert result.final_truth is None
    snapshots = await iterations.list_iteration_snapshots(run_id="run-1")
    assert len(snapshots) == target and len(native_children) == target
    assert all(item.request_payload["deadline_utc"] == payload["deadline_utc"] for item in snapshots)
    assert snapshots[-1].result_payload is None


@dataclass(frozen=True)
class _ResumeCase:
    loop: GovernedAgentLoopService
    execution: AsyncControlPlaneExecutionRepository
    iterations: AsyncGovernedAgentRepository
    resume: GovernedAgentEffectResumeService
    resumed: GovernedAgentResumePreparation
    acceptance: CheckpointAcceptanceRecord
    now: datetime


async def _prepare_resume_case(tmp_path: Path, *, handshake_timeout=None) -> _ResumeCase:
    await AsyncFileTools(tmp_path).write_file("inputs/tickets.json", {"source": "fixture"})
    db_path = tmp_path / "agent-effect-loop.sqlite3"
    execution = AsyncControlPlaneExecutionRepository(db_path)
    iterations = AsyncGovernedAgentRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    loop = _loop(execution, iterations, records, handshake_timeout=handshake_timeout)
    request_payload = _effect_request()
    now = datetime.now(UTC)
    first = await _run_loop(
        loop, request_payload, now,
        decisions=((now + timedelta(seconds=1)).isoformat(), (now + timedelta(seconds=2)).isoformat()),
        lease_expiries=((now + timedelta(seconds=7)).isoformat(),),
    )
    assert first.run.lifecycle_state is RunState.OPERATOR_BLOCKED
    assert first.decisions[0].rule == "effect_approval_required"
    snapshot = (await iterations.list_iteration_snapshots(run_id="run-1"))[0]
    assert snapshot.result_payload is not None
    request = AgentIterationRequest.from_wire(snapshot.request_payload)
    proposals = [AgentEffectProposal.from_wire(item) for item in snapshot.result_payload["effect_proposals"]]
    result = AgentIterationResult.from_wire(snapshot.result_payload)
    publication = ControlPlanePublicationService(repository=records)
    receipts = await _approve_effects(tmp_path, execution, publication, request, proposals, now)
    acceptance = await _accept_checkpoint(records, publication, request, result, now)
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
    return _ResumeCase(loop, execution, iterations, resume, resumed, acceptance, now)


async def _approve_effects(tmp_path, execution, publication, request, proposals, now):
    db_path = tmp_path / "agent-effect-loop.sqlite3"
    effects = GovernedAgentEffectService(
        transactions=SQLiteControlPlaneTransactions(db_path),
        execution_repository=execution,
        publication=publication,
        pending_gates=AsyncPendingGateRepository(db_path),
        file_executor=GovernedAgentFileEffectExecutor(tmp_path, tool_gate=ToolGate(None, tmp_path)),
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
    return receipts


async def _accept_checkpoint(records, publication, request, result, now):
    journals = tuple(await records.list_effect_journal_entries(run_id="run-1"))
    checkpoint = aggregate_effect_checkpoint(
        request,
        result,
        journals,
        (now + timedelta(seconds=5)).isoformat(),
    )
    return await publication.accept_checkpoint(
        acceptance_id="agent-effects-checkpoint-acceptance:agent-invocation:run-1:00000001",
        checkpoint=checkpoint,
        supervisor_authority_ref="governed-agent-effect-control-service:v1",
        decision_timestamp=(now + timedelta(seconds=5)).isoformat(),
        required_reobservation_class=CheckpointReobservationClass.NONE,
        integrity_verification_ref=checkpoint.integrity_verification_ref,
        journal_entries=journals,
        dependent_effect_entry_refs=tuple(entry.journal_entry_id for entry in journals),
    )


async def _run_loop(loop, request_payload, now, *, decisions, lease_expiries):
    return await loop.run_bounded(
        initial_request_payload=request_payload,
        workload_record=agent_workload_record(),
        extension_digest="sha256:" + "e" * 64,
        configuration_digest="sha256:" + "c" * 64,
        admission_receipt_ref="agent-admission:test",
        creation_timestamp_utc=now.isoformat(),
        decision_timestamps_utc=decisions,
        next_lease_expiries_utc=lease_expiries,
    )


def _loop(execution, iterations, records, *, handshake_timeout=None) -> GovernedAgentLoopService:
    provider = DeterministicModelProvider()
    broker = GovernedAgentHostBroker(
        iteration_repository=iterations,
        call_repository=iterations,
        model_provider=provider,
        model_profiles=resolved_profiles(),
    )
    # Positive effect/resume proof uses the production startup allowance. The
    # explicit expiry case retains the old two-second boundary; request/lease
    # limits remain the original eight/seven seconds in every case.
    options = {} if handshake_timeout is None else {"handshake_timeout_seconds": handshake_timeout}
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent",
        allowed_stdlib_modules=("json",),
        broker=broker,
        **options,
    )
    return GovernedAgentLoopService(
        execution_repository=execution,
        iteration_repository=iterations,
        transactions=SQLiteControlPlaneTransactions(records.db_path),
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
