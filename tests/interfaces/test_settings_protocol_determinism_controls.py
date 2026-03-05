from __future__ import annotations

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import app


client = TestClient(app)


def test_runtime_policy_options_exposes_protocol_determinism_fields(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.get("/v1/system/runtime-policy/options", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_ledger_mode"]["default"] == "sqlite"
    assert payload["protocol_timezone"]["default"] == "UTC"
    assert payload["protocol_locale"]["default"] == "C.UTF-8"
    assert payload["protocol_network_mode"]["default"] == "off"
    assert payload["protocol_network_allowlist"]["default"] == ""
    assert payload["protocol_env_allowlist"]["default"] == ""
    assert payload["protocol_timezone"]["input_style"] == "text"
    assert payload["protocol_locale"]["input_style"] == "text"
    assert payload["protocol_network_mode"]["input_style"] == "radio"
    assert payload["protocol_network_allowlist"]["input_style"] == "text"
    assert payload["protocol_env_allowlist"]["input_style"] == "text"


def test_runtime_policy_get_resolves_protocol_determinism_precedence(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "dual_write")
    monkeypatch.setenv("ORKET_PROTOCOL_TIMEZONE", "America/Denver")
    monkeypatch.setenv("ORKET_PROTOCOL_LOCALE", "en_US.UTF-8")
    monkeypatch.setenv("ORKET_PROTOCOL_NETWORK_MODE", "allowlist")
    monkeypatch.setenv("ORKET_PROTOCOL_NETWORK_ALLOWLIST", "api.example.com,cache.example.com")
    monkeypatch.setenv("ORKET_PROTOCOL_ENV_ALLOWLIST", "HOME,PATH")
    monkeypatch.setattr(
        api_module,
        "load_user_settings",
        lambda: {
            "run_ledger_mode": "sqlite",
            "protocol_timezone": "UTC",
            "protocol_locale": "C.UTF-8",
            "protocol_network_mode": "off",
            "protocol_network_allowlist": "",
            "protocol_env_allowlist": "",
        },
    )
    monkeypatch.setattr(
        api_module.engine,
        "org",
        type(
            "Org",
            (),
            {
                "process_rules": {
                    "run_ledger_mode": "protocol",
                    "protocol_timezone": "America/Chicago",
                    "protocol_locale": "en_US.UTF-8",
                    "protocol_network_mode": "allowlist",
                    "protocol_network_allowlist": "api.example.com",
                    "protocol_env_allowlist": "HOME",
                }
            },
        )(),
    )

    response = client.get("/v1/system/runtime-policy", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_ledger_mode"] == "dual_write"
    assert payload["protocol_timezone"] == "America/Denver"
    assert payload["protocol_locale"] == "en_US.UTF-8"
    assert payload["protocol_network_mode"] == "allowlist"
    assert payload["protocol_network_allowlist"] == "api.example.com,cache.example.com"
    assert payload["protocol_env_allowlist"] == "HOME,PATH"


def test_runtime_policy_update_saves_protocol_determinism_fields(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"existing": True})
    monkeypatch.setattr(api_module, "save_user_settings", lambda settings: captured.update({"settings": settings}))

    response = client.post(
        "/v1/system/runtime-policy",
        json={
            "run_ledger_mode": "dual_write",
            "protocol_timezone": "America/Denver",
            "protocol_locale": "en_US.UTF-8",
            "protocol_network_mode": "allowlist",
            "protocol_network_allowlist": "api.example.com,cache.example.com",
            "protocol_env_allowlist": "HOME,PATH",
        },
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["settings"]["run_ledger_mode"] == "dual_write"
    assert captured["settings"]["protocol_timezone"] == "America/Denver"
    assert captured["settings"]["protocol_locale"] == "en_US.UTF-8"
    assert captured["settings"]["protocol_network_mode"] == "allowlist"
    assert captured["settings"]["protocol_network_allowlist"] == "api.example.com,cache.example.com"
    assert captured["settings"]["protocol_env_allowlist"] == "HOME,PATH"


def test_settings_patch_accepts_protocol_determinism_fields(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())
    captured = {}
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {"existing": "x"})
    monkeypatch.setattr(api_module, "save_user_settings", lambda settings: captured.update({"settings": settings}))

    response = client.patch(
        "/v1/settings",
        json={
            "run_ledger_mode": "dual_write",
            "protocol_timezone": "America/Denver",
            "protocol_locale": "en_US.UTF-8",
            "protocol_network_mode": "allowlist",
            "protocol_network_allowlist": "api.example.com,cache.example.com",
            "protocol_env_allowlist": "HOME,PATH",
        },
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["settings"]["run_ledger_mode"] == "dual_write"
    assert captured["settings"]["protocol_timezone"] == "America/Denver"
    assert captured["settings"]["protocol_locale"] == "en_US.UTF-8"
    assert captured["settings"]["protocol_network_mode"] == "allowlist"
    assert captured["settings"]["protocol_network_allowlist"] == "api.example.com,cache.example.com"
    assert captured["settings"]["protocol_env_allowlist"] == "HOME,PATH"


def test_settings_patch_rejects_invalid_protocol_network_mode(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(api_module.engine, "org", type("Org", (), {"process_rules": {}})())
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})

    response = client.patch(
        "/v1/settings",
        json={"protocol_network_mode": "internet"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(err["field"] == "protocol_network_mode" and err["code"] == "invalid_value" for err in detail["errors"])


def test_settings_get_reports_protocol_determinism_sources(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_PROTOCOL_TIMEZONE", "America/Denver")
    monkeypatch.setenv("ORKET_PROTOCOL_LOCALE", "en_US.UTF-8")
    monkeypatch.setattr(
        api_module,
        "load_user_settings",
        lambda: {
            "run_ledger_mode": "dual_write",
            "protocol_network_mode": "allowlist",
            "protocol_network_allowlist": "api.example.com",
        },
    )
    monkeypatch.setattr(
        api_module.engine,
        "org",
        type(
            "Org",
            (),
            {
                "process_rules": {
                    "protocol_env_allowlist": "HOME,PATH",
                }
            },
        )(),
    )

    response = client.get("/v1/settings", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["protocol_timezone"]["value"] == "America/Denver"
    assert settings["protocol_timezone"]["source"] == "env"
    assert settings["protocol_locale"]["source"] == "env"
    assert settings["protocol_network_mode"]["source"] == "user"
    assert settings["protocol_network_allowlist"]["source"] == "user"
    assert settings["protocol_env_allowlist"]["source"] == "process_rules"
    assert settings["run_ledger_mode"]["source"] == "user"


def test_settings_get_keeps_run_ledger_mode_source_stable_under_env_override(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    monkeypatch.setattr(
        api_module,
        "load_user_settings",
        lambda: {},
    )
    monkeypatch.setattr(
        api_module.engine,
        "org",
        type("Org", (), {"process_rules": {}})(),
    )

    response = client.get("/v1/settings", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["run_ledger_mode"]["value"] == "protocol"
    # Intentional policy: avoid host-env source noise for backend/ledger mode settings.
    assert settings["run_ledger_mode"]["source"] == "default"
