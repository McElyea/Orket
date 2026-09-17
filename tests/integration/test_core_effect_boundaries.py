"""Application-owned core effects over real files, including refusal and cancellation."""

import asyncio
import json
import threading
from pathlib import Path

import pytest

import orket.application.services.failure_report_service as failures
import orket.application.services.structural_reconciliation_service as reconciliation
from orket.adapters.storage.structural_board_store import StructuralBoardStore
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.failure_report_service import FailureReportService
from orket.application.services.tool_gate_service import ToolGate
from orket.core.domain.failure_reporter import FailureReporter
from orket.core.domain.reconciler import StructuralReconciler
from orket.services.ast_validator import ASTValidator
from tests.helpers.core_effect_fixtures import BOARD_ASSETS, TIMESTAMP

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_LIMIT_SECONDS = 0.5


@pytest.fixture
def model_root(tmp_path):
    root = tmp_path / "model"
    for asset in BOARD_ASSETS:
        path = root / asset.relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(asset.content, encoding="utf-8")
    return root


async def test_failure_artifact_and_saved_event_match_explicit_value(tmp_path, monkeypatch):
    """Layer: integration. The saved event observes the complete real artifact."""
    report = FailureReporter.build_report(
        timestamp=TIMESTAMP, session_id="run", card_id="card", violation="tool denied"
    )
    observed = []
    original = failures.log_event

    def capture(name, data, workspace):
        observed.append((name, json.loads(Path(data["path"]).read_text(encoding="utf-8"))))
        original(name, data, workspace)

    monkeypatch.setattr(failures, "log_event", capture)
    path = await FailureReportService(tmp_path).publish(report)
    saved = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
    assert saved == report.model_dump(mode="json")
    assert observed == [("policy_violation_report_saved", saved)]


async def test_invalid_failure_artifact_identity_does_not_escape_workspace(tmp_path):
    """Layer: integration. Invalid artifact identity is refused before any directory or file write."""
    report = FailureReporter.build_report(timestamp=TIMESTAMP, session_id="run", card_id="../escape", violation="x")
    with pytest.raises(ValueError, match="file-name"):
        await FailureReportService(tmp_path).publish(report)
    assert not await asyncio.to_thread((tmp_path / "agent_output").exists)


async def test_reconciliation_events_follow_verified_real_target_writes(model_root, tmp_path, monkeypatch):
    """Layer: integration. Adoption claims match actual target contents and reruns add nothing."""
    observed = []
    original = reconciliation.log_event

    def capture(name, payload, *, workspace):
        if name.endswith("_adopted"):
            is_epic = "epic_id" in payload
            target = "core/rocks/run_the_business.json" if is_epic else "core/epics/unplanned_support.json"
            data = json.loads((model_root / target).read_text(encoding="utf-8"))
            observed.append((name, payload, data))
        original(name, payload, workspace=workspace)

    monkeypatch.setattr(reconciliation, "log_event", capture)
    service = reconciliation.StructuralReconciler(model_root, tmp_path / "workspace")
    plan = await service.reconcile()
    assert plan == StructuralReconciler.plan(BOARD_ASSETS)
    assert observed[0][2]["epics"] == [{"epic": "product_plan", "department": "product"}]
    assert observed[1][2]["issues"] == [{"id": "orphan", "summary": "Unplanned work"}]
    assert not (await service.reconcile()).writes
    assert len(observed) == 2


async def test_invalid_issue_is_not_written_or_reported_adopted(model_root, tmp_path, monkeypatch):
    """Layer: integration. Reproduced malformed-input false success is now an explicit refusal."""
    await asyncio.to_thread((model_root / "product/issues/orphan.json").write_text, "{broken", encoding="utf-8")
    events = []
    monkeypatch.setattr(reconciliation, "log_event", lambda name, *args, **kwargs: events.append(name))
    with pytest.raises(reconciliation.StructuralReconciliationError, match="orphan.json"):
        await reconciliation.StructuralReconciler(model_root, tmp_path / "workspace").reconcile()
    for asset in BOARD_ASSETS[:2]:
        assert await asyncio.to_thread((model_root / asset.relative_path).read_text, encoding="utf-8") == asset.content
    assert events == ["reconciler_start"]


async def test_target_drift_is_refused_without_overwriting_operator_state(model_root):
    """Layer: integration. A changed target is preserved and no temporary artifact survives refusal."""
    store = StructuralBoardStore(model_root)
    plan = StructuralReconciler.plan(await store.snapshot())
    target = model_root / plan.writes[0].relative_path
    await asyncio.to_thread(target.write_text, '{"operator": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="changed after snapshot"):
        await store.apply(plan.writes[0])
    assert await asyncio.to_thread(target.read_text, encoding="utf-8") == '{"operator": true}'


async def test_reconciliation_drains_cancelled_write_and_keeps_loop_responsive(model_root, tmp_path, monkeypatch):
    """Layer: integration. An admitted real write remains owned until it settles after cancellation."""
    started, release = threading.Event(), threading.Event()
    original = StructuralBoardStore._apply_sync

    def held_write(store, update):
        started.set()
        if not release.wait(4):
            raise TimeoutError("fixture write was not released")
        original(store, update)

    monkeypatch.setattr(StructuralBoardStore, "_apply_sync", held_write)
    task = asyncio.create_task(reconciliation.StructuralReconciler(model_root, tmp_path / "workspace").reconcile())
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 3), 3.5)
        await asyncio.wait_for(asyncio.sleep(0), RESPONSIVENESS_LIMIT_SECONDS)
        task.cancel()
        await asyncio.sleep(0.03)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    data = json.loads(
        await asyncio.to_thread((model_root / "core/rocks/run_the_business.json").read_text, encoding="utf-8")
    )
    assert data["epics"] == [{"epic": "product_plan", "department": "product"}]


async def test_failed_report_write_emits_no_saved_event(tmp_path, monkeypatch):
    """Layer: integration. A real directory/file collision cannot become a saved report claim."""
    target = tmp_path / "agent_output/policy_violation_card.json"
    await asyncio.to_thread(target.mkdir, parents=True)
    report = FailureReporter.build_report(timestamp=TIMESTAMP, session_id="run", card_id="card", violation="x")
    events = []
    monkeypatch.setattr(failures, "log_event", lambda name, *args, **kwargs: events.append(name))
    with pytest.raises(OSError):
        await FailureReportService(tmp_path).publish(report)
    assert not events and await asyncio.to_thread(target.is_dir)


async def test_application_gate_precedes_real_governed_file_effects(tmp_path):
    """Layer: integration. Explicit gate composition preserves allowed writes and blocks outside writes."""
    with pytest.raises(ValueError, match="tool-gate authority"):
        GovernedAgentFileEffectExecutor(tmp_path, tool_gate=None)
    executor = GovernedAgentFileEffectExecutor(tmp_path, tool_gate=ToolGate(None, tmp_path))
    allowed = await executor.write(path="written.txt", content="verified content", issue_id="issue")
    assert allowed["ok"]
    assert await asyncio.to_thread((tmp_path / "written.txt").read_text, encoding="utf-8") == "verified content"
    denied = await executor.write(path="../outside.txt", content="must not write", issue_id="issue")
    assert not denied["ok"] and "Security violation" in denied["error"]
    assert not await asyncio.to_thread((tmp_path.parent / "outside.txt").exists)


async def test_ast_validation_worker_is_responsive_and_owned_through_cancellation(tmp_path, monkeypatch):
    """Layer: integration. Actual AST validation drains before the cancelled application gate returns."""
    started, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = ASTValidator.validate_code

    def held_validation(content, filename):
        started.set()
        if not release.wait(4):
            raise TimeoutError("fixture validator was not released")
        try:
            return original(content, filename)
        finally:
            settled.set()

    monkeypatch.setattr(ASTValidator, "validate_code", held_validation)
    gate = ToolGate(None, tmp_path)
    task = asyncio.create_task(
        gate.validate(
            "write_file",
            {
                "path": "engines/test_engine.py",
                "content": "class TestEngine: pass\n",
            },
            {"idesign_enabled": True},
            ["developer"],
        )
    )
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 3), 3.5)
        await asyncio.wait_for(asyncio.sleep(0), RESPONSIVENESS_LIMIT_SECONDS)
        task.cancel()
        await asyncio.sleep(0.03)
        assert not task.done() and not settled.is_set()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert settled.is_set()
