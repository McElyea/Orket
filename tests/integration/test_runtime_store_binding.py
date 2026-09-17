"""Real card approval controls for stable runtime and control-plane store ownership."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from orket.orchestration.engine import OrchestrationEngine
from tests.integration.test_epic_approval_continuation import pause
from tests.integration.test_system_acceptance_flow import (
    ToolApprovalContinuationProvider,
    _build_assets,
    _patch_provider,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def stage_project(root, monkeypatch):
    await asyncio.to_thread(root.mkdir, parents=True)
    await asyncio.to_thread(
        _build_assets,
        root,
        with_guard=False,
        epic_id="approval_required",
        expected_file="approved.txt",
        expected_text="approved",
    )
    _patch_provider(monkeypatch, ToolApprovalContinuationProvider())
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(root / ".orket/durable"))


@asynccontextmanager
async def bound_engine(root, workspace, monkeypatch, db_path="state/cards.db"):
    # Provision the old split layout so failures exercise ownership, not missing directories.
    for directory in (root / "state", workspace / "state"):
        await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    engine = await asyncio.to_thread(OrchestrationEngine, workspace, db_path=db_path, config_root=root)
    monkeypatch.setattr(
        engine._pipeline.orchestrator.loop_policy_node,
        "approval_required_tools_for_seat",
        lambda seat_name, **_: ["write_file"] if seat_name == "lead_architect" else [],
    )
    try:
        yield engine
    finally:
        await engine.close()


# Layer: integration
async def test_cwd_change_cannot_redirect_a_pending_card_approval(tmp_path, monkeypatch):
    project, unrelated = tmp_path / "project", tmp_path / "unrelated"
    await stage_project(project, monkeypatch)
    await asyncio.to_thread(unrelated.mkdir)
    monkeypatch.chdir(project)
    async with bound_engine(project, project / "workspace", monkeypatch) as engine:
        approval = await pause(engine)
        monkeypatch.chdir(unrelated)
        result = await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
        assert result["runtime_result"]["succeeded"]
        assert (await engine.run_ledger.get_run("approval-session"))["status"] == "done"
        truth = await engine.control_plane_repository.get_final_truth(run_id=approval["control_plane_target_ref"])
        assert truth is not None and truth.result_class.value == "success"
        assert Path(engine.db_path) == project / "state/cards.db"
        assert not await asyncio.to_thread((unrelated / "state").exists)
        assert (
            await asyncio.to_thread((project / "workspace/agent_output/approved.txt").read_text, encoding="utf-8")
            == "approved"
        )


# Layer: integration
async def test_execution_workspace_does_not_select_another_approval_authority(tmp_path, monkeypatch):
    project = tmp_path / "project"
    await stage_project(project, monkeypatch)
    monkeypatch.chdir(project)
    async with bound_engine(project, project / "first-workspace", monkeypatch) as first:
        approval = await pause(first)
        retained = await first.control_plane_execution_repository.get_run_record(
            run_id=approval["control_plane_target_ref"]
        )
        assert retained is not None
    async with bound_engine(project, project / "second-workspace", monkeypatch) as second:
        observed = await second.control_plane_execution_repository.get_run_record(
            run_id=approval["control_plane_target_ref"]
        )
        assert observed == retained
        assert Path(second.control_plane_repository.db_path) == project / "state/control_plane_records.sqlite3"
        assert not await asyncio.to_thread((project / "second-workspace/state/control_plane_records.sqlite3").exists)


# Layer: integration
async def test_relative_durable_root_is_frozen_for_default_store_owners(tmp_path, monkeypatch):
    project, unrelated = tmp_path / "project", tmp_path / "unrelated"
    await stage_project(project, monkeypatch)
    await asyncio.to_thread(unrelated.mkdir)
    monkeypatch.chdir(project)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", "state")
    async with bound_engine(project, project / "workspace", monkeypatch, db_path=None) as engine:
        approval = await pause(engine)
        monkeypatch.chdir(unrelated)
        outcome = await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
        assert outcome["runtime_result"]["succeeded"]
        assert Path(engine.db_path) == project / "state/db/orket_persistence.db"
        assert Path(engine.control_plane_repository.db_path) == project / "state/db/control_plane_records.sqlite3"
        assert not await asyncio.to_thread((unrelated / "state").exists)
