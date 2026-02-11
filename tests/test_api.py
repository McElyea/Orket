import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from orket.interfaces.api import app
import orket.interfaces.api as api_module
import orket.logging as logging_module
import os

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "organization": "Orket"}

def test_version_unauthenticated():
    # If ORKET_API_KEY is not set, it might pass or fail depending on env
    # For testing, we assume auth is required if the key is present
    response = client.get("/v1/version")
    if os.getenv("ORKET_API_KEY"):
        assert response.status_code == 403
    else:
        assert response.status_code == 200

def test_version_authenticated(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/version", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert "version" in response.json()

def test_heartbeat():
    response = client.get("/v1/system/heartbeat")
    # Heartbeat might be under v1_router which requires auth if configured
    if response.status_code == 403:
        response = client.get("/v1/system/heartbeat", headers={"X-API-Key": os.getenv("ORKET_API_KEY", "")})
    
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "online"
        assert "timestamp" in data

def test_explorer_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to escape PROJECT_ROOT
    response = client.get("/v1/system/explorer?path=../../", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403

def test_read_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to read something sensitive outside root
    response = client.get("/v1/system/read?path=../../etc/passwd", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403

def test_calendar():
    # Public or private? api.py says it's in v1_router
    headers = {"X-API-Key": os.getenv("ORKET_API_KEY", "")}
    response = client.get("/v1/system/calendar", headers=headers)
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert "current_sprint" in data
        assert "sprint_start" in data

def test_metrics():
    headers = {"X-API-Key": os.getenv("ORKET_API_KEY", "")}
    response = client.get("/v1/system/metrics", headers=headers)
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert "cpu" in data
        assert "memory" in data
        assert "timestamp" in data
        datetime.fromisoformat(data["timestamp"])


def test_system_board_uses_dept_query(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    def fake_board(department):
        return {"department": department}

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_system_board", fake_board)

    response = client.get("/v1/system/board?dept=product", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"department": "product"}


def test_preview_asset_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_issue_preview(self, issue_id, asset_name, department):
            return {"mode": "issue", "issue_id": issue_id, "asset_name": asset_name, "department": department}

        async def build_rock_preview(self, asset_name, department):
            return {"mode": "rock", "asset_name": asset_name, "department": department}

        async def build_epic_preview(self, asset_name, department):
            return {"mode": "epic", "asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "issue", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_invocation",
        lambda target, issue_id: {"method_name": "build_issue_preview", "args": [issue_id, target["asset_name"], target["department"]]},
    )
    monkeypatch.setattr(api_module.api_runtime_node, "create_preview_builder", lambda _model_root: FakeBuilder())

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json&issue_id=ISSUE-9",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "issue", "issue_id": "ISSUE-9", "asset_name": "asset-x", "department": "core"}


def test_run_active_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    captured = {}

    async def fake_run(**kwargs):
        captured["kwargs"] = kwargs
        return {"ok": True}

    class FakeEngine:
        run_card = staticmethod(fake_run)

    async def fake_add_task(session_id, task):
        captured["session_id"] = session_id
        await task

    monkeypatch.setattr(api_module, "engine", FakeEngine())
    monkeypatch.setattr(api_module.runtime_state, "add_task", fake_add_task)
    monkeypatch.setattr(api_module.api_runtime_node, "create_session_id", lambda: "SESS1234")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_asset_id", lambda path, issue_id: "ISSUE-1")
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_run_active_invocation",
        lambda asset_id, build_id, session_id, request_type: {
            "method_name": "run_card",
            "kwargs": {"card_id": asset_id, "build_id": build_id, "session_id": session_id},
        },
    )

    response = client.post(
        "/v1/system/run-active",
        json={"path": "model/core/issues/demo.json", "build_id": "B1", "type": "issue"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "SESS1234"}
    assert captured["session_id"] == "SESS1234"
    assert captured["kwargs"] == {"card_id": "ISSUE-1", "build_id": "B1", "session_id": "SESS1234"}


def test_run_active_rejects_unsupported_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "create_session_id", lambda: "SESSX")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_asset_id", lambda path, issue_id: "ISSUE-1")
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_run_active_invocation",
        lambda asset_id, build_id, session_id, request_type: {
            "method_name": "does_not_exist",
            "kwargs": {},
        },
    )

    response = client.post(
        "/v1/system/run-active",
        json={"path": "model/core/issues/demo.json", "type": "issue"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "Unsupported run method" in response.json()["detail"]


def test_run_metrics_uses_runtime_workspace(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    captured = {}

    def fake_workspace(project_root, session_id):
        captured["workspace_args"] = (project_root, session_id)
        return project_root / "workspace" / "runs" / session_id

    def fake_member_metrics(workspace):
        captured["metrics_workspace"] = workspace
        return {"ok": True, "workspace": str(workspace)}

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_member_metrics_workspace", fake_workspace)
    monkeypatch.setattr(logging_module, "get_member_metrics", fake_member_metrics)

    response = client.get("/v1/runs/SESS42/metrics", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["workspace"].endswith("workspace\\runs\\SESS42")
    assert captured["workspace_args"][1] == "SESS42"


def test_sandbox_logs_uses_runtime_pipeline_factory(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    captured = {}

    class FakeSandboxOrchestrator:
        def get_logs(self, sandbox_id, service):
            captured["log_args"] = (sandbox_id, service)
            return "fake-logs"

    class FakePipeline:
        sandbox_orchestrator = FakeSandboxOrchestrator()

    def fake_workspace(project_root):
        captured["workspace_root"] = project_root
        return project_root / "workspace" / "default"

    def fake_create_pipeline(workspace_root):
        captured["pipeline_workspace"] = workspace_root
        return FakePipeline()

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_sandbox_workspace", fake_workspace)
    monkeypatch.setattr(api_module.api_runtime_node, "create_execution_pipeline", fake_create_pipeline)

    response = client.get(
        "/v1/sandboxes/sb-1/logs?service=api",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"logs": "fake-logs"}
    assert captured["log_args"] == ("sb-1", "api")
