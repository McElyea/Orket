import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import app
from orket.schema import CardStatus


client = TestClient(app)


def test_api_expansion_gate_model_assignments_contract(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get(
        "/v1/system/model-assignments?roles=coder,reviewer",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["filters"]["roles"] == ["coder", "reviewer"]
    assert isinstance(payload["generated_at"], str)
    for item in payload["items"]:
        assert set(item.keys()) >= {"role", "selected_model", "final_model", "demoted", "reason", "dialect"}
        assert item["role"] in {"coder", "reviewer"}
        assert isinstance(item["selected_model"], str)
        assert isinstance(item["final_model"], str)
        assert isinstance(item["demoted"], bool)


@pytest.mark.asyncio
async def test_api_expansion_gate_execution_graph_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    session_id = "GATE-GRAPH-1"
    await real_engine.sessions.start_session(
        session_id,
        {"type": "epic", "name": "gate-graph", "department": "core", "task_input": "demo"},
    )
    await real_engine.cards.save(
        {
            "id": "ROOT",
            "session_id": session_id,
            "build_id": "BUILD-GATE",
            "seat": "COD-1",
            "summary": "Root",
            "priority": 2.0,
            "depends_on": [],
        }
    )
    await real_engine.cards.save(
        {
            "id": "CHILD",
            "session_id": session_id,
            "build_id": "BUILD-GATE",
            "seat": "REV-1",
            "summary": "Child",
            "priority": 2.0,
            "depends_on": ["ROOT"],
        }
    )

    response = client.get(f"/v1/runs/{session_id}/execution-graph", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert payload["has_cycle"] is False
    assert payload["execution_order"] == ["ROOT", "CHILD"]
    assert payload["edges"] == [{"source": "ROOT", "target": "CHILD"}]

    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes["ROOT"]["blocked"] is False
    assert nodes["CHILD"]["blocked"] is True
    assert nodes["CHILD"]["blocked_by"] == ["ROOT"]


def test_api_expansion_gate_token_summary_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module, "PROJECT_ROOT", Path(tmp_path))

    async def fake_get_run(session_id):
        return {"session_id": session_id}

    async def fake_get_session(session_id):
        return {"id": session_id}

    monkeypatch.setattr(api_module.engine.run_ledger, "get_run", fake_get_run)
    monkeypatch.setattr(api_module.engine.sessions, "get_session", fake_get_session)

    default_workspace = Path(tmp_path) / "workspace" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)
    log_path = default_workspace / "orket.log"
    lines = [
        {
            "timestamp": "2026-02-16T12:00:00+00:00",
            "role": "coder",
            "event": "turn_start",
            "data": {
                "runtime_event": {
                    "session_id": "GATE-TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "GATE-TOK-1:ISS-1:coder:1",
                    "selected_model": "qwen2.5-coder:14b",
                }
            },
        },
        {
            "timestamp": "2026-02-16T12:00:01+00:00",
            "role": "coder",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "GATE-TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "GATE-TOK-1:ISS-1:coder:1",
                    "tokens": {"total_tokens": 21},
                }
            },
        },
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")

    response = client.get("/v1/runs/GATE-TOK-1/token-summary", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tokens"] == 21
    assert payload["turn_count"] == 1
    assert payload["by_role"] == [{"role": "coder", "tokens_total": 21}]
    assert payload["by_model"] == [{"model": "qwen2.5-coder:14b", "tokens_total": 21}]
    assert payload["by_role_model"] == [{"role": "coder", "model": "qwen2.5-coder:14b", "tokens_total": 21}]
    assert payload["turns"][0]["turn_trace_id"] == "GATE-TOK-1:ISS-1:coder:1"


def test_api_expansion_gate_system_teams_contract(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/system/teams?department=core", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "count" in payload
    assert payload["filters"]["department"] == "core"
    assert isinstance(payload["items"], list)
    if payload["items"]:
        team = payload["items"][0]
        assert set(team.keys()) >= {"department", "team_id", "name", "seats", "roles"}
        assert isinstance(team["seats"], list)
        assert isinstance(team["roles"], list)


@pytest.mark.asyncio
async def test_api_expansion_gate_card_guard_history_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    await real_engine.cards.save(
        {
            "id": "CARD-GUARD-1",
            "session_id": "S-G1",
            "build_id": "B-G1",
            "seat": "REV-1",
            "summary": "Guard card",
            "priority": 2.0,
        }
    )
    await real_engine.cards.update_status("CARD-GUARD-1", CardStatus.AWAITING_GUARD_REVIEW, assignee="guard")
    await real_engine.cards.update_status("CARD-GUARD-1", CardStatus.GUARD_REQUESTED_CHANGES, assignee="guard")
    await real_engine.cards.update_status("CARD-GUARD-1", CardStatus.AWAITING_GUARD_REVIEW, assignee="guard")
    await real_engine.cards.update_status("CARD-GUARD-1", CardStatus.GUARD_APPROVED, assignee="guard")

    response = client.get("/v1/cards/CARD-GUARD-1/guard-history", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["card_id"] == "CARD-GUARD-1"
    assert payload["count"] == 4
    assert payload["summary"]["awaiting_guard_review"] == 2
    assert payload["summary"]["guard_requested_changes"] == 1
    assert payload["summary"]["guard_approved"] == 1
    assert payload["summary"]["retry_count"] == 1

