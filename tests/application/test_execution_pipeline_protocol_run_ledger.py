from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.exceptions import ExecutionFailed
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus


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
            "description": "Protocol run ledger test",
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
async def test_execution_pipeline_supports_protocol_run_ledger_incomplete_path(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "protocol_ledger_epic_incomplete")
    protocol_repo = AsyncProtocolRunLedgerRepository(workspace)
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=protocol_repo,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-03-05/sess-protocol-incomplete",
            "commit": "abc123",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    await pipeline.run_epic(
        "protocol_ledger_epic_incomplete",
        build_id="build-protocol-ledger-epic-incomplete",
        session_id="sess-protocol-incomplete",
    )

    run = await protocol_repo.get_run("sess-protocol-incomplete")
    assert run is not None
    assert run["status"] == "incomplete"
    assert run["summary_json"]["session_status"] == "incomplete"
    assert run["artifact_json"]["workspace"] == str(workspace)
    assert run["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert run["started_event_seq"] == 1
    assert run["ended_event_seq"] == 2


@pytest.mark.asyncio
async def test_execution_pipeline_supports_protocol_run_ledger_failure_path(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "protocol_ledger_epic_failed")
    protocol_repo = AsyncProtocolRunLedgerRepository(workspace)
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=protocol_repo,
    )

    async def _raise_execute_epic(**_kwargs):
        raise ExecutionFailed("forced protocol failure")

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-03-05/sess-protocol-failed",
            "commit": "def456",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _raise_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    with pytest.raises(ExecutionFailed, match="forced protocol failure"):
        await pipeline.run_epic(
            "protocol_ledger_epic_failed",
            build_id="build-protocol-ledger-epic-failed",
            session_id="sess-protocol-failed",
        )

    run = await protocol_repo.get_run("sess-protocol-failed")
    assert run is not None
    assert run["status"] == "failed"
    assert run["failure_class"] == "ExecutionFailed"
    assert "forced protocol failure" in str(run["failure_reason"] or "")
    assert run["summary_json"]["session_status"] == "failed"
    assert run["artifact_json"]["gitea_export"]["provider"] == "gitea"
    assert run["artifact_json"]["gitea_export"]["commit"] == "def456"


@pytest.mark.asyncio
async def test_execution_pipeline_protocol_run_ledger_terminal_failure_path(
    test_root,
    workspace,
    db_path,
    monkeypatch,
):
    _write_epic_assets(test_root, "protocol_ledger_epic_terminal_failure")
    protocol_repo = AsyncProtocolRunLedgerRepository(workspace)
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        run_ledger_repo=protocol_repo,
    )

    async def _blocked_execute_epic(**_kwargs):
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.BLOCKED)
        return None

    async def _fake_export_run(**_kwargs):
        return {
            "provider": "gitea",
            "owner": "local",
            "repo": "artifacts",
            "branch": "main",
            "path": "runs/2026-03-05/sess-protocol-terminal-failure",
            "commit": "xyz789",
            "url": "http://localhost:3000/local/artifacts",
        }

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _blocked_execute_epic)
    monkeypatch.setattr(pipeline.artifact_exporter, "export_run", _fake_export_run)

    await pipeline.run_epic(
        "protocol_ledger_epic_terminal_failure",
        build_id="build-protocol-ledger-epic-terminal-failure",
        session_id="sess-protocol-terminal-failure",
    )

    run = await protocol_repo.get_run("sess-protocol-terminal-failure")
    assert run is not None
    assert run["status"] == "terminal_failure"
    assert run["summary_json"]["session_status"] == "terminal_failure"
    assert run["summary_json"]["status_counts"]["blocked"] == 1
