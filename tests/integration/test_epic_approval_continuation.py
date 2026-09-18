"""Integration proof of the parent epic and governed child approval lifecycle."""
import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI

from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.interfaces.routers.approvals import build_approvals_router
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.execution.epic_run_orchestrator import EpicRunOrchestrator
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_system_acceptance_flow import (
    ToolApprovalContinuationProvider,
    _build_assets,
    _patch_provider,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("decision", ["approve", "deny"])
# Layer: integration
async def test_approval_http_response_distinguishes_decision_from_runtime_outcome(
    tmp_path, monkeypatch, decision, deterministic_turn_clock,
):
    """Real ASGI route/stores with ordered turn time; reversal has separate rollback controls."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        before = deterministic_turn_clock()
        observed = engine._pipeline.orchestrator.issue_control_plane.now_utc()
        assert before < observed < deterministic_turn_clock()
        approval = await pause(engine)
        app = FastAPI()
        app.include_router(build_approvals_router(lambda: engine), prefix="/v1")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(f"/v1/approvals/{approval['approval_id']}/decision", json={"decision": decision})
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "resolved"
        result = payload["runtime_result"]
        assert result["observation"] == "published" and result["succeeded"] is (decision == "approve")
        assert result["final_truth"]["result_class"] == ("success" if decision == "approve" else "failed")
        assert result["publication_ref"] in result["evidence_refs"]
        ledger = await engine.run_ledger.get_run("approval-session")
        assert ledger["status"] == ("done" if decision == "approve" else "failed")


@asynccontextmanager
async def approval_engine(root, monkeypatch, *, setup=False, custom_db=False):
    workspace = root / "workspace"
    if setup:
        await asyncio.to_thread(workspace.mkdir)
        await asyncio.to_thread(_build_assets, root, with_guard=False, epic_id="approval_required",
                                expected_file="approved.txt", expected_text="approved")
    _patch_provider(monkeypatch, ToolApprovalContinuationProvider())
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket" / "durable"))
    engine = await asyncio.to_thread(
        OrchestrationEngine, workspace, department="core",
        db_path=str(root / "custom/cards.db" if custom_db else root / ".orket/durable/db/orket_persistence.db"), config_root=root)
    monkeypatch.setattr(engine._pipeline.orchestrator.loop_policy_node, "approval_required_tools_for_seat",
                        lambda seat_name, **_: ["write_file"] if seat_name == "lead_architect" else [])
    try:
        yield engine
    finally:
        await engine.close()


async def pause(engine):
    outcome = await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build")
    assert outcome.observation == "approval_pending" and not outcome.succeeded
    assert outcome.final_truth is None and outcome.evidence_refs
    approvals = await engine.list_approvals(status="PENDING")
    assert len(approvals) == 1
    ledger = await engine._pipeline.run_ledger.get_run("approval-session")
    assert ledger["status"] == "running"
    async with engine._pipeline.epic_publication.repository.transaction("approval-session") as transaction:
        assert await transaction.get_outcome() is None
        assert await transaction.get() is None
        assert (await transaction.get_admission()).phase == "active"
    return approvals[0]


@pytest.mark.parametrize("decision", ["approve", "deny"])
@pytest.mark.parametrize("custom_db", [False, True])
# Layer: integration
async def test_epic_approval_survives_restart_with_parent_truth(tmp_path, monkeypatch, decision, custom_db):
    """Layer: integration. Restart retains pause, authority, and the original parent/child identities."""
    async with approval_engine(tmp_path, monkeypatch, setup=True, custom_db=custom_db) as engine:
        approval = await pause(engine)
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)
    async with approval_engine(tmp_path, monkeypatch, custom_db=custom_db) as engine:
        result = await engine.decide_approval(approval_id=approval["approval_id"], decision=decision)
        assert result["approval"]["status"] == {"approve": "APPROVED", "deny": "DENIED"}[decision]
        assert result["runtime_result"]["succeeded"] is (decision == "approve")
        ledger = await engine._pipeline.run_ledger.get_run("approval-session")
        assert ledger["status"] == ("done" if decision == "approve" else "failed")
        truth = await engine.control_plane_repository.get_final_truth(run_id=approval["control_plane_target_ref"])
        assert truth is not None
        assert truth.result_class.value == ("success" if decision == "approve" else "blocked")
        output = tmp_path / "workspace/agent_output/approved.txt"
        assert await asyncio.to_thread(output.exists) == (decision == "approve")
        if decision == "approve":
            assert await asyncio.to_thread(output.read_text, encoding="utf-8") == "approved"
        again = await engine.decide_approval(approval_id=approval["approval_id"], decision=decision)
        assert again["status"] == "idempotent"
        assert await engine._pipeline.run_ledger.get_run("approval-session") == ledger
        async with engine._pipeline.epic_publication.repository.transaction("approval-session") as transaction:
            assert (await transaction.get_admission()).phase == "released"


# Layer: integration
async def test_pending_approval_preserves_admission_and_refuses_dispatch(tmp_path, monkeypatch):
    """Layer: integration. Pending and competing callers cannot reset or dispatch paused cards."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        await pause(engine)
        ledger = await engine._pipeline.run_ledger.get_run("approval-session")
        outcome = await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build")
        assert outcome.observation == "approval_pending" and not outcome.succeeded
        with pytest.raises(ValueError, match="E_EPIC_ADMISSION_RESOURCE_BUSY"):
            await engine.run_card("approval_required", session_id="competing", build_id="approval-build")
        assert await engine._pipeline.run_ledger.get_run("approval-session") == ledger
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)


# Layer: integration
async def test_changed_request_refuses_then_identical_decision_recovers(tmp_path, monkeypatch):
    """Layer: integration. A stored decision does not bypass the retained request on reentry."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        approval = await pause(engine)
    path = tmp_path / "model/core/environments/standard.json"
    original = await asyncio.to_thread(path.read_text, encoding="utf-8")
    changed = {**json.loads(original), "temperature": 0.7}
    await asyncio.to_thread(path.write_text, json.dumps(changed), encoding="utf-8")
    async with approval_engine(tmp_path, monkeypatch) as engine:
        with pytest.raises(ValueError, match="E_EPIC_APPROVAL_REQUEST_CONFLICT"):
            await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)
    await asyncio.to_thread(path.write_text, original, encoding="utf-8")
    async with approval_engine(tmp_path, monkeypatch) as engine:
        result = await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
        assert result["status"] == "idempotent"
        assert (await engine._pipeline.run_ledger.get_run("approval-session"))["status"] == "done"


# Layer: integration
async def test_concurrent_continuation_consumes_pause_once(tmp_path, monkeypatch):
    """Layer: integration. Separate runtimes contend while the admitted continuation is paused."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as first:
        approval = await pause(first)
        claimed, release = asyncio.Event(), asyncio.Event()
        dispatches = []
        execute = EpicRunOrchestrator._execute_workload

        async def held_execute(owner, context):
            dispatches.append(context.setup.run_id)
            claimed.set()
            await asyncio.wait_for(release.wait(), 15)
            return await execute(owner, context)

        monkeypatch.setattr(EpicRunOrchestrator, "_execute_workload", held_execute)
        async with approval_engine(tmp_path, monkeypatch) as second:
            task = asyncio.create_task(first.decide_approval(approval_id=approval["approval_id"], decision="approve"))
            try:
                await asyncio.wait_for(claimed.wait(), 15)
                observed = await second.decide_approval(approval_id=approval["approval_id"], decision="approve")
                assert observed["runtime_result"]["observation"] == "unresolved"
                assert "E_EPIC_APPROVAL_CONTINUATION_UNCERTAIN" in observed["runtime_result"]["reason"]
                assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)
            finally:
                release.set()
                await asyncio.wait_for(task, 15)
            assert dispatches == ["approval-session"]
            assert (await second._pipeline.run_ledger.get_run("approval-session"))["status"] == "done"


class TwoApprovalProvider(ToolApprovalContinuationProvider):
    async def complete(self, messages):
        result = await super().complete(messages)
        if '"write_file"' in result.content:
            next_write = '```json\n{"tool":"write_file","args":{"path":"agent_output/second.txt","content":"second"}}\n```\n'
            result.content = result.content.replace('```json\n{"tool": "update_issue_status"',
                                                    next_write + '```json\n{"tool": "update_issue_status"', 1)
        return result


# Layer: integration
async def test_post_effect_pause_cannot_widen_pre_effect_continuation(tmp_path, monkeypatch):
    """Layer: integration. Later effect history cannot inherit pre-effect continuation authority."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        _patch_provider(monkeypatch, TwoApprovalProvider())
        first = await pause(engine)
        await engine.decide_approval(approval_id=first["approval_id"], decision="approve")
        pending = await engine.list_approvals(status="PENDING")
        assert len(pending) == 1
        second = pending[0]
        assert second["control_plane_target_ref"] == first["control_plane_target_ref"]
        assert second["approval_id"] != first["approval_id"]
        assert (await engine._pipeline.run_ledger.get_run("approval-session"))["status"] == "running"
        assert await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").read_text, encoding="utf-8") == "approved"
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/second.txt").exists)
    async with approval_engine(tmp_path, monkeypatch) as engine:
        observed = await engine.decide_approval(approval_id=second["approval_id"], decision="approve")
        assert observed["runtime_result"]["observation"] == "published"
        assert not observed["runtime_result"]["succeeded"]
        assert "beyond the pre-effect checkpoint" in observed["runtime_result"]["reason"]
        assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/second.txt").exists)
        assert await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").read_text, encoding="utf-8") == "approved"
        assert (await engine._pipeline.run_ledger.get_run("approval-session"))["status"] == "failed"
        async with engine._pipeline.epic_publication.repository.transaction("approval-session") as tx:
            checkpoint = await tx.approval_pauses.latest()
            assert checkpoint.sequence == 2
            assert set(checkpoint.decisions) == {first["approval_id"], second["approval_id"]}


# Layer: integration
async def test_approval_and_denial_race_has_one_durable_winner(tmp_path, monkeypatch):
    """Layer: integration. Separate SQLite decision writers cannot overwrite the winning decision."""
    async with approval_engine(tmp_path, monkeypatch, setup=True) as first:
        approval = await pause(first)
        original = AsyncPendingGateRepository.resolve_request
        ready, arrivals = asyncio.Event(), []

        async def synchronized_decision(repository, **kwargs):
            arrivals.append(kwargs["status"])
            if len(arrivals) == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), 15)
            return await original(repository, **kwargs)

        monkeypatch.setattr(AsyncPendingGateRepository, "resolve_request", synchronized_decision)
        async with approval_engine(tmp_path, monkeypatch) as second:
            results = await asyncio.wait_for(asyncio.gather(
                first.decide_approval(approval_id=approval["approval_id"], decision="approve"),
                second.decide_approval(approval_id=approval["approval_id"], decision="deny"),
                return_exceptions=True), 30)
            successes = [result for result in results if isinstance(result, dict)]
            failures = [result for result in results if isinstance(result, RuntimeError)]
            assert len(successes) == len(failures) == 1
            assert "conflicting decision" in str(failures[0])
            status = successes[0]["approval"]["status"]
            retained = await first.get_approval(approval["approval_id"])
            assert retained["status"] == status
            ledger = await first._pipeline.run_ledger.get_run("approval-session")
            assert ledger["status"] == ("done" if status == "APPROVED" else "failed")
            assert await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists) == (status == "APPROVED")
