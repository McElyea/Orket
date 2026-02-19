import asyncio
import json
import pytest
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from orket.interfaces.api import app
import orket.interfaces.api as api_module
from orket.schema import CardStatus
import os

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "organization": "Orket"}

def test_version_unauthenticated():
    response = client.get("/v1/version")
    assert response.status_code == 403


def test_version_allows_explicit_insecure_bypass(monkeypatch):
    monkeypatch.delenv("ORKET_API_KEY", raising=False)
    monkeypatch.setenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "true")
    response = client.get("/v1/version")
    assert response.status_code == 200

def test_version_authenticated(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/version", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert "version" in response.json()


def test_auth_uses_runtime_invalid_detail(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "api_key_invalid_detail", lambda: "Auth denied by policy")
    response = client.get("/v1/version", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Auth denied by policy"

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


def test_clear_logs_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeFs:
        async def clear_sink(self, path, content):
            captured["args"] = (path, content)

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_clear_logs_path",
        lambda: "workspace/default/orket.log",
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_clear_logs_invocation",
        lambda log_path: {"method_name": "clear_sink", "args": [log_path, ""]},
    )

    response = client.post("/v1/system/clear-logs", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["args"] == ("workspace/default/orket.log", "")


def test_clear_logs_rejects_unsupported_runtime_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def write_file(self, path, content):
            return None

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_clear_logs_invocation",
        lambda log_path: {"method_name": "missing_method", "args": [log_path, ""]},
    )

    response = client.post("/v1/system/clear-logs", headers={"X-API-Key": "test-key"})
    assert response.status_code == 400
    assert "Unsupported clear logs method" in response.json()["detail"]


def test_clear_logs_suppresses_permission_errors(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeFs:
        async def write_file(self, path, content):
            raise PermissionError("denied")

    def fake_log_event(name, payload, workspace=None):
        captured["event"] = (name, payload)

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(api_module, "log_event", fake_log_event)

    response = client.post("/v1/system/clear-logs", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["event"][0] == "clear_logs_skipped"
    assert "denied" in captured["event"][1]["error"]


def test_explorer_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to escape PROJECT_ROOT
    response = client.get("/v1/system/explorer?path=../../", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403


def test_explorer_uses_runtime_forbidden_error_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_explorer_path", lambda project_root, path: None)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_explorer_forbidden_error",
        lambda path: {"status_code": 451, "detail": f"Blocked path: {path}"},
    )

    response = client.get("/v1/system/explorer?path=../../", headers={"X-API-Key": "test-key"})
    assert response.status_code == 451
    assert response.json()["detail"] == "Blocked path: ../../"


def test_explorer_uses_runtime_missing_response_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_explorer_path",
        lambda project_root, path: project_root / "does-not-exist",
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_explorer_missing_response",
        lambda path: {"items": [], "path": path, "source": "runtime-policy"},
    )

    response = client.get("/v1/system/explorer?path=does-not-exist", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "path": "does-not-exist", "source": "runtime-policy"}

def test_read_security(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    # Try to read something sensitive outside root
    response = client.get("/v1/system/read?path=../../etc/passwd", headers={"X-API-Key": "test-key"})
    assert response.status_code == 403

def test_read_missing_file_returns_404(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def read_file(self, path):
            raise FileNotFoundError(path)

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    response = client.get("/v1/system/read?path=missing.txt", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_read_uses_runtime_not_found_detail(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def read_file(self, path):
            raise FileNotFoundError(path)

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "read_not_found_detail",
        lambda path: f"Missing by policy: {path}",
    )

    response = client.get("/v1/system/read?path=missing.txt", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Missing by policy: missing.txt"

def test_read_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeFs:
        async def read_file(self, path):
            captured["path"] = path
            return "ok-content"

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_read_invocation",
        lambda path: {"method_name": "read_file", "args": [path]},
    )

    response = client.get("/v1/system/read?path=foo.txt", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"content": "ok-content"}
    assert captured["path"] == "foo.txt"

def test_read_rejects_unsupported_runtime_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def read_file(self, path):
            return "ignored"

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_read_invocation",
        lambda path: {"method_name": "nope", "args": [path]},
    )

    response = client.get("/v1/system/read?path=foo.txt", headers={"X-API-Key": "test-key"})
    assert response.status_code == 400

def test_save_permission_denied_returns_403(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def write_file(self, path, content):
            raise PermissionError("blocked")

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    response = client.post(
        "/v1/system/save",
        json={"path": "x.txt", "content": "hello"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 403


def test_save_uses_runtime_permission_denied_detail(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def write_file(self, path, content):
            raise PermissionError("blocked")

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "permission_denied_detail",
        lambda operation, error: f"{operation} denied by policy: {error}",
    )
    response = client.post(
        "/v1/system/save",
        json={"path": "x.txt", "content": "hello"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "save denied by policy: blocked"

def test_save_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeFs:
        async def write_file(self, path, content):
            captured["args"] = (path, content)

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_save_invocation",
        lambda path, content: {"method_name": "write_file", "args": [path, content]},
    )
    response = client.post(
        "/v1/system/save",
        json={"path": "x.txt", "content": "hello"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["args"] == ("x.txt", "hello")

def test_save_rejects_unsupported_runtime_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeFs:
        async def write_file(self, path, content):
            return None

    monkeypatch.setattr(api_module.api_runtime_node, "create_file_tools", lambda _root: FakeFs())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_save_invocation",
        lambda path, content: {"method_name": "nope", "args": [path, content]},
    )
    response = client.post(
        "/v1/system/save",
        json={"path": "x.txt", "content": "hello"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400

def test_calendar():
    # Public or private? api.py says it's in v1_router
    headers = {"X-API-Key": os.getenv("ORKET_API_KEY", "")}
    response = client.get("/v1/system/calendar", headers=headers)
    assert response.status_code in [200, 403]
    if response.status_code == 200:
        data = response.json()
        assert "current_sprint" in data
        assert "sprint_start" in data


def test_calendar_uses_runtime_current_sprint_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_current_sprint", lambda now: "QX SY")
    response = client.get("/v1/system/calendar", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["current_sprint"] == "QX SY"


def test_runtime_policy_options(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/system/runtime-policy/options", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["architecture_mode"]["input_style"] == "radio"
    assert data["frontend_framework_mode"]["input_style"] == "radio"
    assert data["project_surface_profile"]["input_style"] == "radio"
    assert data["small_project_builder_variant"]["input_style"] == "radio"
    assert data["state_backend_mode"]["input_style"] == "radio"
    assert data["gitea_state_pilot_enabled"]["input_style"] == "radio"
    assert data["architecture_mode"]["default"] == "force_monolith"
    assert "microservices_pilot_stable" in data["architecture_mode"]
    assert data["frontend_framework_mode"]["default"] == "force_vue"
    assert data["project_surface_profile"]["default"] == "unspecified"
    assert data["small_project_builder_variant"]["default"] == "auto"
    assert data["state_backend_mode"]["default"] == "local"
    assert data["gitea_state_pilot_enabled"]["default"] is False


def test_model_assignments_endpoint_returns_selector_decisions(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module, "_discover_active_roles", lambda _root: ["coder", "reviewer"])
    monkeypatch.setattr(api_module, "load_user_preferences", lambda: {"models": {"coder": "qwen2.5-coder:14b"}})
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})

    class FakeSelector:
        def __init__(self, organization=None, preferences=None, user_settings=None):
            self._role = None

        def select(self, role, department="core", override=None, asset_config=None):
            self._role = role
            if role == "coder":
                return "qwen2.5-coder:14b"
            return "llama3.1:8b"

        def get_last_selection_decision(self):
            if self._role == "coder":
                return {
                    "selected_model": "qwen2.5-coder:14b",
                    "final_model": "qwen2.5-coder:14b",
                    "demoted": False,
                    "reason": "score_ok",
                }
            return {
                "selected_model": "llama3.1:8b",
                "final_model": "llama3.1:8b",
                "demoted": False,
                "reason": "fallback",
            }

        def get_dialect_name(self, model):
            return "qwen" if "qwen" in model else "llama3"

    monkeypatch.setattr(api_module, "ModelSelector", FakeSelector)

    response = client.get("/v1/system/model-assignments", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["filters"]["roles"] is None
    assert payload["items"][0]["role"] == "coder"
    assert payload["items"][0]["selected_model"] == "qwen2.5-coder:14b"
    assert payload["items"][0]["final_model"] == "qwen2.5-coder:14b"
    assert payload["items"][0]["reason"] == "score_ok"
    assert payload["items"][1]["role"] == "reviewer"
    assert "generated_at" in payload


def test_model_assignments_endpoint_respects_role_filter(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module, "load_user_preferences", lambda: {})
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})

    class FakeSelector:
        def __init__(self, organization=None, preferences=None, user_settings=None):
            self._role = None

        def select(self, role, department="core", override=None, asset_config=None):
            self._role = role
            return "llama3.1:8b"

        def get_last_selection_decision(self):
            return {
                "selected_model": "llama3.1:8b",
                "final_model": "llama3.1:8b",
                "demoted": False,
                "reason": "fallback",
            }

        def get_dialect_name(self, model):
            return "llama3"

    monkeypatch.setattr(api_module, "ModelSelector", FakeSelector)

    response = client.get(
        "/v1/system/model-assignments?roles= coder, reviewer ,coder",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["filters"]["roles"] == ["coder", "reviewer"]
    assert [item["role"] for item in payload["items"]] == ["coder", "reviewer"]


def test_runtime_policy_get_uses_precedence(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "true")
    monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_microservices")
    monkeypatch.setenv("ORKET_FRONTEND_FRAMEWORK_MODE", "force_angular")
    monkeypatch.setenv("ORKET_PROJECT_SURFACE_PROFILE", "api_vue")
    monkeypatch.setenv("ORKET_SMALL_PROJECT_BUILDER_VARIANT", "architect")
    monkeypatch.setenv("ORKET_STATE_BACKEND_MODE", "gitea")
    monkeypatch.setenv("ORKET_ENABLE_GITEA_STATE_PILOT", "true")
    monkeypatch.setenv("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", "benchmarks/results/nonexistent_pilot_stability.json")
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"architecture_mode": "force_monolith"})
    monkeypatch.setattr(
        api_module.engine,
        "org",
        type("Org", (), {"process_rules": {"architecture_mode": "force_monolith", "frontend_framework_mode": "force_vue"}})(),
    )

    response = client.get("/v1/system/runtime-policy", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {
        "architecture_mode": "force_microservices",
        "frontend_framework_mode": "force_angular",
        "project_surface_profile": "api_vue",
        "small_project_builder_variant": "architect",
        "state_backend_mode": "gitea",
        "gitea_state_pilot_enabled": True,
        "default_architecture_mode": "force_monolith",
        "allowed_architecture_patterns": ["monolith", "microservices"],
        "microservices_unlocked": True,
        "microservices_pilot_stable": False,
    }


def test_runtime_policy_get_falls_back_to_monolith_when_microservices_locked(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "false")
    monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_microservices")
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())

    response = client.get("/v1/system/runtime-policy", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["architecture_mode"] == "force_monolith"
    assert response.json()["microservices_unlocked"] is False


def test_runtime_policy_reports_pilot_stability(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "true")
    report_path = tmp_path / "pilot_stability.json"
    report_path.write_text('{"stable": true}', encoding="utf-8")
    monkeypatch.setenv("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", str(report_path))
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())

    response = client.get("/v1/system/runtime-policy", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["microservices_pilot_stable"] is True


def test_runtime_policy_update_normalizes_and_saves(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"existing": True})
    monkeypatch.setattr(api_module, "save_user_settings", lambda settings: captured.update({"settings": settings}))

    response = client.post(
        "/v1/system/runtime-policy",
        json={
            "architecture_mode": "monolith",
            "frontend_framework_mode": "vue",
            "project_surface_profile": "backend",
            "small_project_builder_variant": "architect",
            "state_backend_mode": "gitea",
            "gitea_state_pilot_enabled": True,
        },
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["settings"]["architecture_mode"] == "force_monolith"
    assert captured["settings"]["frontend_framework_mode"] == "force_vue"
    assert captured["settings"]["project_surface_profile"] == "backend_only"
    assert captured["settings"]["small_project_builder_variant"] == "architect"
    assert captured["settings"]["state_backend_mode"] == "gitea"
    assert captured["settings"]["gitea_state_pilot_enabled"] is True


def test_settings_get_returns_metadata_and_sources(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "true")
    monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_microservices")
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"frontend_framework_mode": "force_react"})
    monkeypatch.setattr(
        api_module.engine,
        "org",
        type("Org", (), {"process_rules": {"project_surface_profile": "backend_only"}})(),
    )

    response = client.get("/v1/settings", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["architecture_mode"]["value"] == "force_microservices"
    assert settings["architecture_mode"]["source"] == "env"
    assert settings["frontend_framework_mode"]["source"] == "user"
    assert settings["project_surface_profile"]["source"] == "process_rules"
    assert settings["state_backend_mode"]["source"] == "default"
    assert "force_monolith" in settings["architecture_mode"]["allowed_values"]
    assert settings["gitea_state_pilot_enabled"]["type"] == "boolean"


def test_settings_patch_round_trip_persists_normalized_values(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "true")
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())
    captured = {}
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"existing": "x"})
    monkeypatch.setattr(api_module, "save_user_settings", lambda settings: captured.update({"settings": settings}))

    response = client.patch(
        "/v1/settings",
        json={
            "architecture_mode": "microservices",
            "frontend_framework_mode": "react",
            "project_surface_profile": "backend",
            "small_project_builder_variant": "architect",
            "state_backend_mode": "local",
            "gitea_state_pilot_enabled": "enabled",
        },
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["settings"]["architecture_mode"] == "force_microservices"
    assert captured["settings"]["frontend_framework_mode"] == "force_react"
    assert captured["settings"]["project_surface_profile"] == "backend_only"
    assert captured["settings"]["small_project_builder_variant"] == "architect"
    assert captured["settings"]["state_backend_mode"] == "local"
    assert captured["settings"]["gitea_state_pilot_enabled"] is True


def test_settings_patch_rejects_invalid_values_structured(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())

    response = client.patch(
        "/v1/settings",
        json={"frontend_framework_mode": "svelte", "unknown_field": "x"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "Invalid settings update"
    assert any(err["field"] == "frontend_framework_mode" and err["code"] == "invalid_value" for err in detail["errors"])
    assert any(err["field"] == "unknown_field" and err["code"] == "unknown_setting" for err in detail["errors"])


def test_settings_patch_enforces_policy_guards(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "false")
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())

    response = client.patch(
        "/v1/settings",
        json={"architecture_mode": "force_microservices"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any(err["field"] == "architecture_mode" and err["code"] == "policy_guard" for err in errors)


def test_settings_patch_rejects_gitea_without_pilot(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_GITEA_STATE_PILOT", raising=False)
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())

    response = client.patch(
        "/v1/settings",
        json={"state_backend_mode": "gitea", "gitea_state_pilot_enabled": False},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any(err["field"] == "state_backend_mode" and err["code"] == "policy_guard" for err in errors)

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

def test_system_board_defaults_to_core(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_board(department):
        captured["department"] = department
        return {"department": department}

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_system_board", fake_board)

    response = client.get("/v1/system/board", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"department": "core"}
    assert captured["department"] == "core"


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
        lambda target, issue_id: {
            "method_name": "build_issue_preview",
            "args": [issue_id, target["asset_name"], target["department"]],
            "unsupported_detail": "Unsupported preview mode 'issue'.",
        },
    )
    monkeypatch.setattr(api_module.api_runtime_node, "create_preview_builder", lambda _model_root: FakeBuilder())

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json&issue_id=ISSUE-9",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json() == {"mode": "issue", "issue_id": "ISSUE-9", "asset_name": "asset-x", "department": "core"}


def test_preview_asset_rejects_unsupported_mode(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_epic_preview(self, asset_name, department):
            return {"asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "custom", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_invocation",
        lambda target, issue_id: {
            "method_name": "build_custom_preview",
            "args": [target["asset_name"], target["department"]],
            "unsupported_detail": "Unsupported preview mode 'custom'.",
        },
    )
    monkeypatch.setattr(api_module.api_runtime_node, "create_preview_builder", lambda _model_root: FakeBuilder())

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "Unsupported preview mode" in response.json()["detail"]


def test_preview_asset_uses_runtime_error_detail_for_unsupported_mode(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeBuilder:
        async def build_epic_preview(self, asset_name, department):
            return {"asset_name": asset_name, "department": department}

    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_target",
        lambda path, issue_id: {"mode": "custom", "asset_name": "asset-x", "department": "core"},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_preview_invocation",
        lambda target, issue_id: {
            "method_name": "build_custom_preview",
            "args": [target["asset_name"], target["department"]],
            "unsupported_detail": f"Unsupported preview invocation 'build_custom_preview' for mode '{target['mode']}'",
        },
    )
    monkeypatch.setattr(api_module.api_runtime_node, "create_preview_builder", lambda _model_root: FakeBuilder())

    response = client.get(
        "/v1/system/preview-asset?path=model/core/epics/x.json",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported preview invocation 'build_custom_preview' for mode 'custom'"


def test_chat_driver_uses_runtime_invocation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeDriver:
        async def process_custom(self, message):
            captured["message"] = message
            return f"echo:{message}"

    monkeypatch.setattr(api_module.api_runtime_node, "create_chat_driver", lambda: FakeDriver())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_chat_driver_invocation",
        lambda message: {"method_name": "process_custom", "args": [message]},
    )

    response = client.post(
        "/v1/system/chat-driver",
        json={"message": "hello"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"response": "echo:hello"}
    assert captured["message"] == "hello"


def test_chat_driver_rejects_unsupported_runtime_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeDriver:
        async def process_request(self, message):
            return f"echo:{message}"

    monkeypatch.setattr(api_module.api_runtime_node, "create_chat_driver", lambda: FakeDriver())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_chat_driver_invocation",
        lambda message: {"method_name": "missing_method", "args": [message]},
    )

    response = client.post(
        "/v1/system/chat-driver",
        json={"message": "hello"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "Unsupported chat driver method" in response.json()["detail"]


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


def test_run_active_uses_runtime_missing_asset_detail(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "create_session_id", lambda: "SESSX")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_asset_id", lambda path, issue_id: None)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "run_active_missing_asset_detail",
        lambda: "Asset is required by policy.",
    )

    response = client.post(
        "/v1/system/run-active",
        json={"path": "", "type": "issue"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Asset is required by policy."


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
    monkeypatch.setattr(api_module.api_runtime_node, "create_member_metrics_reader", lambda: fake_member_metrics)

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


def test_sandbox_logs_forwards_optional_service_param(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeSandboxOrchestrator:
        def get_logs(self, sandbox_id, service):
            captured["log_args"] = (sandbox_id, service)
            return "fake-logs"

    class FakePipeline:
        sandbox_orchestrator = FakeSandboxOrchestrator()

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_sandbox_workspace", lambda root: root / "workspace" / "default")
    monkeypatch.setattr(api_module.api_runtime_node, "create_execution_pipeline", lambda _workspace_root: FakePipeline())

    response = client.get(
        "/v1/sandboxes/sb-1/logs",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"logs": "fake-logs"}
    assert captured["log_args"] == ("sb-1", None)


def test_sandbox_logs_use_runtime_invocation_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    class FakeSandboxOrchestrator:
        def fetch_logs(self, sandbox_id, service):
            captured["log_args"] = (sandbox_id, service)
            return "policy-logs"

    class FakePipeline:
        sandbox_orchestrator = FakeSandboxOrchestrator()

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_sandbox_workspace", lambda root: root / "workspace" / "default")
    monkeypatch.setattr(api_module.api_runtime_node, "create_execution_pipeline", lambda _workspace_root: FakePipeline())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_logs_invocation",
        lambda sandbox_id, service: {"method_name": "fetch_logs", "args": [sandbox_id, service]},
    )

    response = client.get(
        "/v1/sandboxes/sb-9/logs?service=frontend",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"logs": "policy-logs"}
    assert captured["log_args"] == ("sb-9", "frontend")


def test_sandbox_logs_reject_unsupported_runtime_method(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeSandboxOrchestrator:
        def get_logs(self, sandbox_id, service):
            return f"{sandbox_id}:{service}"

    class FakePipeline:
        sandbox_orchestrator = FakeSandboxOrchestrator()

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_sandbox_workspace", lambda root: root / "workspace" / "default")
    monkeypatch.setattr(api_module.api_runtime_node, "create_execution_pipeline", lambda _workspace_root: FakePipeline())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_logs_invocation",
        lambda sandbox_id, service: {"method_name": "missing_logs_method", "args": [sandbox_id, service]},
    )

    response = client.get(
        "/v1/sandboxes/sb-9/logs?service=frontend",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "Unsupported sandbox logs method" in response.json()["detail"]


def test_sandbox_logs_uses_runtime_unsupported_detail(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class FakeSandboxOrchestrator:
        def get_logs(self, sandbox_id, service):
            return f"{sandbox_id}:{service}"

    class FakePipeline:
        sandbox_orchestrator = FakeSandboxOrchestrator()

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_sandbox_workspace", lambda root: root / "workspace" / "default")
    monkeypatch.setattr(api_module.api_runtime_node, "create_execution_pipeline", lambda _workspace_root: FakePipeline())
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_logs_invocation",
        lambda sandbox_id, service: {
            "method_name": "missing_logs_method",
            "args": [sandbox_id, service],
            "unsupported_detail": f"Sandbox log provider unavailable for {sandbox_id}",
        },
    )

    response = client.get(
        "/v1/sandboxes/sb-9/logs?service=frontend",
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Sandbox log provider unavailable for sb-9"


def test_session_detail_returns_404_when_missing(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_session(_session_id):
        return None

    monkeypatch.setattr(api_module.engine.sessions, "get_session", fake_get_session)

    response = client.get("/v1/sessions/NOPE", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_session_snapshot_returns_404_when_missing(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_snapshot(_session_id):
        return None

    monkeypatch.setattr(api_module.engine.snapshots, "get", fake_get_snapshot)

    response = client.get("/v1/sessions/NOPE/snapshot", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_session_detail_uses_runtime_not_found_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_session(_session_id):
        return None

    monkeypatch.setattr(api_module.engine.sessions, "get_session", fake_get_session)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "session_detail_not_found_error",
        lambda session_id: {"status_code": 410, "detail": f"Session '{session_id}' expired"},
    )

    response = client.get("/v1/sessions/NOPE", headers={"X-API-Key": "test-key"})
    assert response.status_code == 410
    assert response.json()["detail"] == "Session 'NOPE' expired"


def test_session_snapshot_uses_runtime_not_found_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_snapshot(_session_id):
        return None

    monkeypatch.setattr(api_module.engine.snapshots, "get", fake_get_snapshot)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "session_snapshot_not_found_error",
        lambda session_id: {"status_code": 410, "detail": f"Snapshot for '{session_id}' expired"},
    )

    response = client.get("/v1/sessions/NOPE/snapshot", headers={"X-API-Key": "test-key"})
    assert response.status_code == 410
    assert response.json()["detail"] == "Snapshot for 'NOPE' expired"


def test_sandboxes_list_and_stop(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_get_sandboxes():
        return [{"id": "sb-1"}]

    async def fake_stop_sandbox(sandbox_id):
        captured["stopped"] = sandbox_id

    monkeypatch.setattr(api_module.engine, "get_sandboxes", fake_get_sandboxes)
    monkeypatch.setattr(api_module.engine, "stop_sandbox", fake_stop_sandbox)

    list_response = client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"})
    stop_response = client.post("/v1/sandboxes/sb-1/stop", headers={"X-API-Key": "test-key"})

    assert list_response.status_code == 200
    assert list_response.json() == [{"id": "sb-1"}]
    assert stop_response.status_code == 200
    assert stop_response.json() == {"ok": True}
    assert captured["stopped"] == "sb-1"


def test_sandboxes_endpoint_no_crash_real_path(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_sandboxes_use_runtime_invocation_policies(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_get_sandboxes():
        captured["list_called"] = True
        return [{"id": "sb-2"}]

    async def fake_stop_sandbox(sandbox_id):
        captured["stop_called"] = sandbox_id

    monkeypatch.setattr(api_module.engine, "get_sandboxes", fake_get_sandboxes)
    monkeypatch.setattr(api_module.engine, "stop_sandbox", fake_stop_sandbox)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandboxes_list_invocation",
        lambda: {"method_name": "get_sandboxes", "args": []},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_stop_invocation",
        lambda sandbox_id: {"method_name": "stop_sandbox", "args": [sandbox_id]},
    )

    list_response = client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"})
    stop_response = client.post("/v1/sandboxes/sb-2/stop", headers={"X-API-Key": "test-key"})

    assert list_response.status_code == 200
    assert list_response.json() == [{"id": "sb-2"}]
    assert stop_response.status_code == 200
    assert captured["list_called"] is True
    assert captured["stop_called"] == "sb-2"


def test_sandboxes_reject_unsupported_runtime_methods(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandboxes_list_invocation",
        lambda: {"method_name": "nope", "args": []},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_stop_invocation",
        lambda _sandbox_id: {"method_name": "nope", "args": []},
    )

    assert client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"}).status_code == 400
    assert client.post("/v1/sandboxes/sb-2/stop", headers={"X-API-Key": "test-key"}).status_code == 400


def test_runs_and_backlog_delegation(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_recent_runs():
        return [{"session_id": "S1"}]

    async def fake_backlog(session_id):
        return [{"id": "I1", "session_id": session_id}]

    monkeypatch.setattr(api_module.engine.sessions, "get_recent_runs", fake_recent_runs)
    monkeypatch.setattr(api_module.engine.sessions, "get_session_issues", fake_backlog, raising=False)

    runs_response = client.get("/v1/runs", headers={"X-API-Key": "test-key"})
    backlog_response = client.get("/v1/runs/S1/backlog", headers={"X-API-Key": "test-key"})

    assert runs_response.status_code == 200
    assert runs_response.json() == [{"session_id": "S1"}]
    assert backlog_response.status_code == 200
    assert backlog_response.json() == [{"id": "I1", "session_id": "S1"}]


@pytest.mark.asyncio
async def test_runs_backlog_real_runtime_repository_success(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    await real_engine.sessions.start_session(
        "REAL-1",
        {"type": "issue", "name": "real", "department": "core", "task_input": "test"},
    )
    await real_engine.cards.save(
        {
            "id": "ISSUE-REAL-1",
            "session_id": "REAL-1",
            "build_id": "BUILD-REAL",
            "seat": "COD-1",
            "summary": "Real backlog item",
            "priority": 2.0,
        }
    )

    response = client.get("/v1/runs/REAL-1/backlog", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["id"] == "ISSUE-REAL-1"
    assert payload[0]["session_id"] == "REAL-1"


@pytest.mark.asyncio
async def test_runs_backlog_real_runtime_repository_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    await real_engine.sessions.start_session(
        "REAL-EMPTY",
        {"type": "issue", "name": "real-empty", "department": "core", "task_input": "test"},
    )

    response = client.get("/v1/runs/REAL-EMPTY/backlog", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_cards_endpoints_real_runtime_filters_and_pagination(monkeypatch, tmp_path):
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
            "id": "CARD-A",
            "session_id": "S-A",
            "build_id": "B-1",
            "seat": "COD-1",
            "summary": "Alpha",
            "priority": 2.0,
        }
    )
    await real_engine.cards.save(
        {
            "id": "CARD-B",
            "session_id": "S-B",
            "build_id": "B-2",
            "seat": "COD-1",
            "summary": "Beta",
            "priority": 2.0,
        }
    )
    await real_engine.cards.update_status("CARD-B", CardStatus.DONE)

    response = client.get(
        "/v1/cards?build_id=B-2&status=done&limit=1&offset=0",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["filters"]["build_id"] == "B-2"
    assert payload["filters"]["status"] == "done"
    assert payload["items"][0]["id"] == "CARD-B"
    assert "created_at" in payload["items"][0]


@pytest.mark.asyncio
async def test_cards_detail_history_comments_real_runtime(monkeypatch, tmp_path):
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
            "id": "CARD-HIST",
            "session_id": "S-H",
            "build_id": "B-H",
            "seat": "REV-1",
            "summary": "History card",
            "priority": 2.0,
        }
    )
    await real_engine.cards.update_status("CARD-HIST", CardStatus.IN_PROGRESS, assignee="tester")
    await real_engine.cards.add_comment("CARD-HIST", "tester", "first comment")

    detail_response = client.get("/v1/cards/CARD-HIST", headers={"X-API-Key": "test-key"})
    history_response = client.get("/v1/cards/CARD-HIST/history", headers={"X-API-Key": "test-key"})
    comments_response = client.get("/v1/cards/CARD-HIST/comments", headers={"X-API-Key": "test-key"})

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "CARD-HIST"

    assert history_response.status_code == 200
    assert history_response.json()["card_id"] == "CARD-HIST"
    assert len(history_response.json()["history"]) >= 1

    assert comments_response.status_code == 200
    assert comments_response.json()["card_id"] == "CARD-HIST"
    assert comments_response.json()["comments"][0]["content"] == "first comment"


def test_cards_detail_history_comments_missing_card(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    detail_response = client.get("/v1/cards/DOES-NOT-EXIST", headers={"X-API-Key": "test-key"})
    history_response = client.get("/v1/cards/DOES-NOT-EXIST/history", headers={"X-API-Key": "test-key"})
    comments_response = client.get("/v1/cards/DOES-NOT-EXIST/comments", headers={"X-API-Key": "test-key"})

    assert detail_response.status_code == 404
    assert history_response.status_code == 404
    assert comments_response.status_code == 404


@pytest.mark.asyncio
async def test_run_detail_and_session_status_real_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    session_id = "RUN-REAL-1"
    await real_engine.sessions.start_session(
        session_id,
        {"type": "epic", "name": "real-run", "department": "core", "task_input": "demo"},
    )
    await real_engine.cards.save(
        {
            "id": "ISSUE-RUN-1",
            "session_id": session_id,
            "build_id": "BUILD-RUN",
            "seat": "COD-1",
            "summary": "Run issue",
            "priority": 2.0,
        }
    )
    await real_engine.run_ledger.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="real-run",
        department="core",
        build_id="BUILD-RUN",
        summary={"phase": "execute"},
        artifacts={"report_path": "runs/report.json"},
    )
    await real_engine.run_ledger.finalize_run(
        session_id=session_id,
        status="done",
        summary={"result": "ok"},
        artifacts={"bundle": "artifact.zip"},
    )

    detail_response = client.get(f"/v1/runs/{session_id}", headers={"X-API-Key": "test-key"})
    status_response = client.get(f"/v1/sessions/{session_id}/status", headers={"X-API-Key": "test-key"})

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["session_id"] == session_id
    assert detail_payload["status"] == "done"
    assert detail_payload["summary"]["result"] == "ok"
    assert detail_payload["artifacts"]["bundle"] == "artifact.zip"
    assert detail_payload["issue_count"] >= 1

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["session_id"] == session_id
    assert status_payload["status"] == "done"
    assert status_payload["backlog"]["count"] >= 1


@pytest.mark.asyncio
async def test_session_halt_endpoint_cancels_runtime_task(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine
    from orket.state import runtime_state

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    async def _sleepy():
        await asyncio.sleep(30)

    task = asyncio.create_task(_sleepy())
    session_id = "HALT-REAL-1"
    await runtime_state.add_task(session_id, task)

    response = client.post(f"/v1/sessions/{session_id}/halt", headers={"X-API-Key": "test-key"})
    await asyncio.sleep(0)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["session_id"] == session_id
    assert task.cancelled() or task.done()

    await runtime_state.remove_task(session_id)


@pytest.mark.asyncio
async def test_session_replay_endpoint_real_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    run_root = workspace_root / "observability" / "RUN-REPLAY-1" / "ISSUE-REPLAY-1" / "001_developer"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "checkpoint.json").write_text(json.dumps({"run_id": "RUN-REPLAY-1"}), encoding="utf-8")
    (run_root / "messages.json").write_text(json.dumps([{"role": "system", "content": "x"}]), encoding="utf-8")
    (run_root / "model_response.txt").write_text("ok", encoding="utf-8")
    (run_root / "parsed_tool_calls.json").write_text(json.dumps([{"tool": "write_file"}]), encoding="utf-8")

    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    response = client.get(
        "/v1/sessions/RUN-REPLAY-1/replay?issue_id=ISSUE-REPLAY-1&turn_index=1&role=developer",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint"]["run_id"] == "RUN-REPLAY-1"
    assert payload["messages"][0]["role"] == "system"
    assert payload["model_response"] == "ok"
    assert payload["parsed_tool_calls"][0]["tool"] == "write_file"


def test_run_detail_and_replay_404_paths(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    run_detail = client.get("/v1/runs/NOPE-RUN", headers={"X-API-Key": "test-key"})
    replay = client.get(
        "/v1/sessions/NOPE/replay?issue_id=ISSUE-1&turn_index=1&role=developer",
        headers={"X-API-Key": "test-key"},
    )
    assert run_detail.status_code == 404
    assert replay.status_code == 404


@pytest.mark.asyncio
async def test_run_replay_list_endpoint_returns_turn_index_for_timeline(monkeypatch, tmp_path):
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
            "timestamp": "2026-02-19T01:00:00+00:00",
            "role": "coder",
            "event": "turn_start",
            "data": {
                "runtime_event": {
                    "session_id": "REP-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "REP-1:ISS-1:coder:1",
                    "selected_model": "qwen2.5-coder:14b",
                }
            },
        },
        {
            "timestamp": "2026-02-19T01:00:01+00:00",
            "role": "coder",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "REP-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "REP-1:ISS-1:coder:1",
                }
            },
        },
        {
            "timestamp": "2026-02-19T01:00:02+00:00",
            "role": "reviewer",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "REP-1",
                    "issue_id": "ISS-1",
                    "turn_index": 2,
                    "turn_trace_id": "REP-1:ISS-1:reviewer:2",
                }
            },
        },
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")

    response = client.get("/v1/runs/REP-1/replay", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "REP-1"
    assert payload["turn_count"] == 2
    assert payload["turns"][0]["issue_id"] == "ISS-1"
    assert payload["turns"][0]["turn_index"] == 1
    assert payload["turns"][0]["role"] == "coder"
    assert payload["turns"][0]["selected_model"] == "qwen2.5-coder:14b"
    assert payload["turns"][1]["turn_index"] == 2


@pytest.mark.asyncio
async def test_session_replay_endpoint_without_target_returns_timeline(monkeypatch, tmp_path):
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
            "timestamp": "2026-02-19T02:00:00+00:00",
            "role": "coder",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "REP-2",
                    "issue_id": "ISS-2",
                    "turn_index": 1,
                    "turn_trace_id": "REP-2:ISS-2:coder:1",
                }
            },
        }
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")

    response = client.get("/v1/sessions/REP-2/replay", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "REP-2"
    assert payload["turn_count"] == 1
    assert payload["turns"][0]["issue_id"] == "ISS-2"
    assert payload["turns"][0]["turn_index"] == 1

@pytest.mark.asyncio
async def test_execution_graph_endpoint_real_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    from orket.orchestration.engine import OrchestrationEngine

    workspace_root = Path(tmp_path) / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(Path(tmp_path) / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    session_id = "GRAPH-REAL-1"
    await real_engine.sessions.start_session(
        session_id,
        {"type": "epic", "name": "graph-run", "department": "core", "task_input": "demo"},
    )
    await real_engine.cards.save(
        {
            "id": "A",
            "session_id": session_id,
            "build_id": "B-GRAPH",
            "seat": "COD-1",
            "summary": "Root",
            "priority": 2.0,
            "depends_on": [],
        }
    )
    await real_engine.cards.save(
        {
            "id": "B",
            "session_id": session_id,
            "build_id": "B-GRAPH",
            "seat": "COD-1",
            "summary": "Depends on A",
            "priority": 2.0,
            "depends_on": ["A"],
        }
    )
    await real_engine.cards.save(
        {
            "id": "C",
            "session_id": session_id,
            "build_id": "B-GRAPH",
            "seat": "REV-1",
            "summary": "Depends on B",
            "priority": 2.0,
            "depends_on": ["B"],
        }
    )
    await real_engine.cards.save(
        {
            "id": "D",
            "session_id": session_id,
            "build_id": "B-GRAPH",
            "seat": "REV-1",
            "summary": "Depends on missing",
            "priority": 2.0,
            "depends_on": ["X-MISSING"],
        }
    )
    await real_engine.cards.update_status("A", CardStatus.DONE)

    response = client.get(f"/v1/runs/{session_id}/execution-graph", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["session_id"] == session_id
    assert payload["node_count"] == 4
    assert payload["edge_count"] == 2
    assert payload["has_cycle"] is False
    assert payload["cycle_nodes"] == []
    assert payload["execution_order"] == ["A", "B", "C", "D"]

    edges = {(edge["source"], edge["target"]) for edge in payload["edges"]}
    assert ("A", "B") in edges
    assert ("B", "C") in edges

    nodes = {node["id"]: node for node in payload["nodes"]}
    assert nodes["A"]["blocked"] is False
    assert nodes["B"]["blocked"] is False
    assert nodes["C"]["blocked"] is True
    assert nodes["C"]["blocked_by"] == ["B"]
    assert nodes["D"]["blocked"] is True
    assert nodes["D"]["unresolved_dependencies"] == ["X-MISSING"]
    assert nodes["D"]["blocked_by"] == ["X-MISSING"]


def test_execution_graph_endpoint_404_when_run_missing(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/runs/NOPE-RUN/execution-graph", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_run_token_summary_aggregates_by_role_model_and_turn(monkeypatch, tmp_path):
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
                    "session_id": "TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "TOK-1:ISS-1:coder:1",
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
                    "session_id": "TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 1,
                    "turn_trace_id": "TOK-1:ISS-1:coder:1",
                    "tokens": {"total_tokens": 25},
                }
            },
        },
        {
            "timestamp": "2026-02-16T12:00:02+00:00",
            "role": "reviewer",
            "event": "turn_start",
            "data": {
                "runtime_event": {
                    "session_id": "TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 2,
                    "turn_trace_id": "TOK-1:ISS-1:reviewer:2",
                    "selected_model": "llama3.1:8b",
                }
            },
        },
        {
            "timestamp": "2026-02-16T12:00:03+00:00",
            "role": "reviewer",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "TOK-1",
                    "issue_id": "ISS-1",
                    "turn_index": 2,
                    "turn_trace_id": "TOK-1:ISS-1:reviewer:2",
                },
                "tokens": 10,
            },
        },
        {
            "timestamp": "2026-02-16T12:00:04+00:00",
            "role": "coder",
            "event": "turn_complete",
            "data": {
                "runtime_event": {
                    "session_id": "TOK-2",
                    "issue_id": "ISS-X",
                    "turn_index": 1,
                    "turn_trace_id": "TOK-2:ISS-X:coder:1",
                    "tokens": {"total_tokens": 999},
                }
            },
        },
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")

    response = client.get("/v1/runs/TOK-1/token-summary", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["session_id"] == "TOK-1"
    assert payload["total_tokens"] == 35
    assert payload["turn_count"] == 2
    assert payload["turns"][0]["role"] == "coder"
    assert payload["turns"][0]["model"] == "qwen2.5-coder:14b"
    assert payload["turns"][0]["tokens_total"] == 25
    assert payload["turns"][1]["role"] == "reviewer"
    assert payload["turns"][1]["model"] == "llama3.1:8b"
    assert payload["turns"][1]["tokens_total"] == 10

    by_role = {item["role"]: item["tokens_total"] for item in payload["by_role"]}
    by_model = {item["model"]: item["tokens_total"] for item in payload["by_model"]}
    by_role_model = {(item["role"], item["model"]): item["tokens_total"] for item in payload["by_role_model"]}
    assert by_role["coder"] == 25
    assert by_role["reviewer"] == 10
    assert by_model["qwen2.5-coder:14b"] == 25
    assert by_model["llama3.1:8b"] == 10
    assert by_role_model[("coder", "qwen2.5-coder:14b")] == 25
    assert by_role_model[("reviewer", "llama3.1:8b")] == 10


def test_run_token_summary_404_when_run_missing(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/runs/NOPE-RUN/token-summary", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_logs_endpoint_filters_and_paginates(monkeypatch, tmp_path):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module, "PROJECT_ROOT", Path(tmp_path))

    default_workspace = Path(tmp_path) / "workspace" / "default"
    default_workspace.mkdir(parents=True, exist_ok=True)
    log_path = default_workspace / "orket.log"
    lines = [
        {
            "timestamp": "2026-02-15T12:00:00+00:00",
            "role": "coder",
            "event": "turn_start",
            "data": {"runtime_event": {"session_id": "S-1"}},
        },
        {
            "timestamp": "2026-02-15T12:05:00+00:00",
            "role": "code_reviewer",
            "event": "turn_complete",
            "data": {"runtime_event": {"session_id": "S-1"}},
        },
        {
            "timestamp": "2026-02-15T12:10:00+00:00",
            "role": "coder",
            "event": "turn_start",
            "data": {"runtime_event": {"session_id": "S-2"}},
        },
    ]
    log_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")

    response = client.get(
        "/v1/logs?session_id=S-1&role=code_reviewer&limit=10&offset=0",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["count"] == 1
    assert payload["items"][0]["event"] == "turn_complete"
    assert payload["filters"]["session_id"] == "S-1"


def test_logs_endpoint_validates_datetime(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get(
        "/v1/logs?start_time=not-a-date",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "Invalid datetime" in response.json()["detail"]


def test_websocket_events_requires_api_key(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/events"):
            pass


def test_websocket_events_accepts_valid_api_key(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    with client.websocket_connect("/ws/events?api_key=test-key") as ws:
        ws.send_text("ping")


def test_runs_sessions_use_runtime_invocation_policies(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_recent_runs():
        return [{"session_id": "S2"}]

    async def fake_backlog(session_id):
        return [{"id": "I2", "session_id": session_id}]

    async def fake_get_session(session_id):
        return {"session_id": session_id}

    async def fake_get_snapshot(session_id):
        return {"snapshot_id": session_id}

    monkeypatch.setattr(api_module.engine.sessions, "get_recent_runs", fake_recent_runs)
    monkeypatch.setattr(api_module.engine.sessions, "get_session_issues", fake_backlog, raising=False)
    monkeypatch.setattr(api_module.engine.sessions, "get_session", fake_get_session)
    monkeypatch.setattr(api_module.engine.snapshots, "get", fake_get_snapshot)

    monkeypatch.setattr(api_module.api_runtime_node, "resolve_runs_invocation", lambda: {"method_name": "get_recent_runs", "args": []})
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_backlog_invocation",
        lambda session_id: {"method_name": "get_session_issues", "args": [session_id]},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_session_detail_invocation",
        lambda session_id: {"method_name": "get_session", "args": [session_id]},
    )
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_session_snapshot_invocation",
        lambda session_id: {"method_name": "get", "args": [session_id]},
    )

    assert client.get("/v1/runs", headers={"X-API-Key": "test-key"}).json() == [{"session_id": "S2"}]
    assert client.get("/v1/runs/S2/backlog", headers={"X-API-Key": "test-key"}).json() == [{"id": "I2", "session_id": "S2"}]
    assert client.get("/v1/sessions/S2", headers={"X-API-Key": "test-key"}).json() == {"session_id": "S2"}
    assert client.get("/v1/sessions/S2/snapshot", headers={"X-API-Key": "test-key"}).json() == {"snapshot_id": "S2"}


def test_runs_sessions_reject_unsupported_runtime_methods(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_runs_invocation", lambda: {"method_name": "nope", "args": []})
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_backlog_invocation", lambda _s: {"method_name": "nope", "args": []})
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_session_detail_invocation", lambda _s: {"method_name": "nope", "args": []})
    monkeypatch.setattr(api_module.api_runtime_node, "resolve_session_snapshot_invocation", lambda _s: {"method_name": "nope", "args": []})

    assert client.get("/v1/runs", headers={"X-API-Key": "test-key"}).status_code == 400
    assert client.get("/v1/runs/S2/backlog", headers={"X-API-Key": "test-key"}).status_code == 400
    assert client.get("/v1/sessions/S2", headers={"X-API-Key": "test-key"}).status_code == 400
    assert client.get("/v1/sessions/S2/snapshot", headers={"X-API-Key": "test-key"}).status_code == 400


def test_session_endpoints_emit_correlation_logs(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured_events = []

    def fake_log_event(name, payload, workspace=None):
        captured_events.append((name, payload))

    async def fake_get_session(_session_id):
        return {"session_id": "S1", "status": "done"}

    async def fake_get_snapshot(_session_id):
        return {"session_id": "S1", "snapshot": True}

    async def fake_backlog(session_id):
        return [{"id": "I1", "session_id": session_id}]

    monkeypatch.setattr(api_module, "log_event", fake_log_event)
    monkeypatch.setattr(api_module.engine.sessions, "get_session", fake_get_session)
    monkeypatch.setattr(api_module.engine.snapshots, "get", fake_get_snapshot)
    monkeypatch.setattr(api_module.engine.sessions, "get_session_issues", fake_backlog, raising=False)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "create_member_metrics_reader",
        lambda: (lambda workspace: {"workspace": str(workspace)}),
    )

    _ = client.get("/v1/runs/S1/metrics", headers={"X-API-Key": "test-key"})
    _ = client.get("/v1/runs/S1/backlog", headers={"X-API-Key": "test-key"})
    _ = client.get("/v1/sessions/S1", headers={"X-API-Key": "test-key"})
    _ = client.get("/v1/sessions/S1/snapshot", headers={"X-API-Key": "test-key"})

    event_map = {name: payload for name, payload in captured_events}
    assert event_map["api_run_metrics"]["session_id"] == "S1"
    assert event_map["api_backlog"]["session_id"] == "S1"
    assert event_map["api_session_detail"]["session_id"] == "S1"
    assert event_map["api_session_snapshot"]["session_id"] == "S1"


def test_cards_archive_requires_selector(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/cards/archive",
        json={},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert "Provide at least one selector" in response.json()["detail"]


def test_cards_archive_uses_runtime_selector_policy(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.api_runtime_node, "has_archive_selector", lambda *_args: False)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "archive_selector_missing_detail",
        lambda: "Selector policy denied request",
    )
    response = client.post(
        "/v1/cards/archive",
        json={},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Selector policy denied request"


def test_cards_archive_by_ids(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    captured = {}

    async def fake_archive_cards(card_ids, archived_by="system", reason=None):
        captured["args"] = (card_ids, archived_by, reason)
        return {"archived": ["I1"], "missing": ["I2"]}

    monkeypatch.setattr(api_module.engine, "archive_cards", fake_archive_cards)

    response = client.post(
        "/v1/cards/archive",
        json={"card_ids": ["I1", "I2"], "reason": "cleanup", "archived_by": "tester"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["archived_count"] == 1
    assert response.json()["archived_ids"] == ["I1"]
    assert response.json()["missing_ids"] == ["I2"]
    assert captured["args"] == (["I1", "I2"], "tester", "cleanup")


def test_cards_archive_by_build_and_related(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_archive_cards(card_ids, archived_by="system", reason=None):
        return {"archived": card_ids, "missing": []}

    async def fake_archive_build(build_id, archived_by="system", reason=None):
        assert build_id == "build-demo"
        return 2

    async def fake_archive_related_cards(tokens, archived_by="system", reason=None):
        assert tokens == ["demo", "legacy"]
        return {"archived": ["R1"], "missing": []}

    monkeypatch.setattr(api_module.engine, "archive_cards", fake_archive_cards)
    monkeypatch.setattr(api_module.engine, "archive_build", fake_archive_build)
    monkeypatch.setattr(api_module.engine, "archive_related_cards", fake_archive_related_cards)

    response = client.post(
        "/v1/cards/archive",
        json={"build_id": "build-demo", "related_tokens": ["demo", "legacy"]},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["archived_count"] == 3
    assert data["archived_ids"] == ["R1"]


def test_cards_archive_uses_runtime_response_normalization(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_archive_cards(card_ids, archived_by="system", reason=None):
        return {"archived": ["B", "A", "A"], "missing": ["Z", "Z"]}

    monkeypatch.setattr(api_module.engine, "archive_cards", fake_archive_cards)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "normalize_archive_response",
        lambda archived_ids, missing_ids, archived_count: {
            "ok": True,
            "archived_count": 999,
            "archived_ids": sorted(set(archived_ids)),
            "missing_ids": sorted(set(missing_ids)),
            "policy": "custom",
        },
    )

    response = client.post(
        "/v1/cards/archive",
        json={"card_ids": ["I1"]},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "archived_count": 999,
        "archived_ids": ["A", "B"],
        "missing_ids": ["Z"],
        "policy": "custom",
    }
