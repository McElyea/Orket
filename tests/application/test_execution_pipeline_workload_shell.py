from __future__ import annotations

import json

import pytest

from orket.runtime.execution_pipeline import ExecutionPipeline


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_epic_assets(root, epic_id):
    _write_json(
        root / "model" / "core" / "teams" / "standard.json",
        {"name": "standard", "seats": {"lead_architect": {"name": "Lead", "roles": ["lead_architect"]}}},
    )
    _write_json(
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "workload shell test",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [{"id": "ISSUE-1", "summary": "Do work", "seat": "lead_architect", "priority": "High", "depends_on": []}],
        },
    )


@pytest.mark.asyncio
async def test_run_epic_routes_through_workload_shell(test_root, workspace, db_path, monkeypatch):
    _write_epic_assets(test_root, "shell_epic")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    called = {}

    async def _fake_execute(*, contract_payload, execute_fn):
        called["payload"] = contract_payload
        return await execute_fn(None)

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.workload_shell, "execute", _fake_execute)
    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic("shell_epic", build_id="build-shell-epic", session_id="sess-shell-epic")
    assert called["payload"]["workload_type"] == "cards"
    assert called["payload"]["workload_contract_version"] == "workload.contract.v1"
