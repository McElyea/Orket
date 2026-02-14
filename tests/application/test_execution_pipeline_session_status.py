import json
from pathlib import Path

import pytest

from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_run_epic_marks_session_incomplete_when_backlog_not_terminal(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "status_epic.json",
        {
            "id": "status_epic",
            "name": "status_epic",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Session status check",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic("status_epic", build_id="build-status-epic", session_id="sess-status-epic")

    runs = await pipeline.sessions.get_recent_runs(limit=1)
    assert runs[0]["id"] == "sess-status-epic"
    assert runs[0]["status"] == "incomplete"

    issues = await pipeline.async_cards.get_by_build("build-status-epic")
    assert issues[0].status == CardStatus.READY


@pytest.mark.asyncio
async def test_run_epic_marks_terminal_failure_when_backlog_blocked(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_json(
        test_root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        test_root / "model" / "core" / "epics" / "status_epic_blocked.json",
        {
            "id": "status_epic_blocked",
            "name": "status_epic_blocked",
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Session terminal non-success check",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _blocked_execute_epic(**_kwargs):
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _blocked_execute_epic)

    await pipeline.run_epic(
        "status_epic_blocked",
        build_id="build-status-epic-blocked",
        session_id="sess-status-epic-blocked",
    )

    runs = await pipeline.sessions.get_recent_runs(limit=5)
    run = next((r for r in runs if r["id"] == "sess-status-epic-blocked"), None)
    assert run is not None
    assert run["status"] == "terminal_failure"
