from __future__ import annotations

import json
from copy import deepcopy

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


# Layer: integration
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
    execute = pipeline.workload_shell.execute
    start_run = pipeline.run_ledger.start_run
    started = {}

    async def _record_execute(*, contract_payload, execute_fn):
        called["payload"] = contract_payload
        return await execute(contract_payload=contract_payload, execute_fn=execute_fn)

    async def _no_op_execute_epic(**_kwargs):
        return None

    async def _record_start(**kwargs):
        started.update(deepcopy(kwargs["artifacts"]))
        return await start_run(**kwargs)

    monkeypatch.setattr(pipeline.workload_shell, "execute", _record_execute)
    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)
    monkeypatch.setattr(pipeline.run_ledger, "start_run", _record_start)

    try:
        await pipeline.run_epic("shell_epic", build_id="build-shell-epic", session_id="sess-shell-epic")
        ledger = await pipeline.run_ledger.get_run("sess-shell-epic")
    finally:
        await pipeline.close()
    assert ledger["status"] == "incomplete"
    assert called["payload"]["workload_type"] == "cards"
    assert called["payload"]["workload_contract_version"] == "workload.contract.v1"
    workload_record = started["control_plane_workload_record"]
    assert workload_record["workload_id"] == "cards-epic-execution"
    assert workload_record["input_contract_ref"] == "docs/specs/WORKLOAD_CONTRACT_V1.md"
    assert workload_record["workload_digest"].startswith("sha256:")
    run_record = started["control_plane_run_record"]
    attempt_record = started["control_plane_attempt_record"]
    step_record = started["control_plane_step_record"]
    assert ledger["artifact_json"]["control_plane_run_record"]["run_id"] == run_record["run_id"]
    assert run_record["workload_id"] == workload_record["workload_id"]
    assert run_record["lifecycle_state"] == "executing"
    assert run_record["current_attempt_id"] == attempt_record["attempt_id"]
    assert attempt_record["attempt_state"] == "attempt_executing"
    assert step_record["attempt_id"] == attempt_record["attempt_id"]
    assert step_record["step_kind"] == "cards_epic_session_start"
