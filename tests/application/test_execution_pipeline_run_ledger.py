import json
from pathlib import Path

import pytest

from orket.exceptions import ExecutionFailed
from orket.runtime.execution_pipeline import ExecutionPipeline


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_epic_assets(root: Path, epic_id: str) -> None:
    _write_json(
        root / "model" / "core" / "teams" / "standard.json",
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
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Run ledger test",
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


@pytest.mark.asyncio
async def test_run_ledger_records_incomplete_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_incomplete")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-02-13/sess-ledger-incomplete",
            "commit": "abc123",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    await pipeline.run_epic(
        "ledger_epic_incomplete",
        build_id="build-ledger-epic-incomplete",
        session_id="sess-ledger-incomplete",
    )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-incomplete")
    assert ledger is not None
    assert ledger["status"] == "incomplete"
    assert ledger["failure_class"] is None
    assert ledger["failure_reason"] is None
    assert ledger["summary_json"]["session_status"] == "incomplete"
    assert ledger["summary_json"]["status_counts"]["ready"] == 1
    assert ledger["artifact_json"]["workspace"] == str(workspace)
    assert ledger["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert ledger["artifact_json"]["gitea_export"]["commit"] == "abc123"


@pytest.mark.asyncio
async def test_run_ledger_records_failed_run(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "ledger_epic_failed")

    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _raise_execute_epic(**_kwargs):
        raise ExecutionFailed("forced failure for ledger")

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-02-13/sess-ledger-failed",
            "commit": "def456",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _raise_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    with pytest.raises(ExecutionFailed, match="forced failure for ledger"):
        await pipeline.run_epic(
            "ledger_epic_failed",
            build_id="build-ledger-epic-failed",
            session_id="sess-ledger-failed",
        )

    ledger = await pipeline.run_ledger.get_run("sess-ledger-failed")
    assert ledger is not None
    assert ledger["status"] == "failed"
    assert ledger["failure_class"] == "ExecutionFailed"
    assert "forced failure for ledger" in (ledger["failure_reason"] or "")
    assert ledger["summary_json"]["session_status"] == "failed"
    assert ledger["summary_json"]["status_counts"]["ready"] == 1
    assert ledger["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert ledger["artifact_json"]["gitea_export"]["commit"] == "def456"

    runs = await pipeline.sessions.get_recent_runs(limit=5)
    failed_run = next((r for r in runs if r["id"] == "sess-ledger-failed"), None)
    assert failed_run is not None
    assert failed_run["status"] == "failed"
