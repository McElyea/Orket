from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import create_api_app


def test_extension_runtime_routes_available_under_v1_only(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies generic extension runtime routes are mounted on `/v1` and old Companion aliases are gone."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}

    status = client.get("/v1/extensions/orket.companion/runtime/status", headers=headers)
    legacy = client.get("/api/v1/companion/status", headers=headers)

    assert status.status_code == 200
    assert status.json()["ok"] is True
    assert legacy.status_code == 404


def test_extension_runtime_routes_use_only_core_api_key(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies legacy Companion-specific API keys no longer authorize generic extension runtime routes."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_COMPANION_API_KEY", "companion-key")
    client = TestClient(create_api_app(project_root=tmp_path))

    rejected = client.get(
        "/v1/extensions/orket.companion/runtime/status",
        headers={"X-API-Key": "companion-key"},
    )
    accepted = client.get(
        "/v1/extensions/orket.companion/runtime/status",
        headers={"X-API-Key": "core-key"},
    )

    assert rejected.status_code == 403
    assert accepted.status_code == 200


def test_extension_runtime_auth_rejection_emits_core_route_event(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies rejected generic runtime auth emits the shared core-route rejection event."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    captured_events: list[dict[str, object]] = []

    def _fake_log_event(name, payload, workspace=None):  # noqa: ANN001
        del workspace
        if name == "api_auth_rejected" and isinstance(payload, dict):
            captured_events.append(payload)

    monkeypatch.setattr(api_module, "log_event", _fake_log_event)
    client = TestClient(create_api_app(project_root=tmp_path))

    response = client.get(
        "/v1/extensions/orket.companion/runtime/status",
        headers={"X-API-Key": "wrong-key"},
    )

    assert response.status_code == 403
    assert any(
        str(event.get("route_class")) == "core"
        and str(event.get("reason")) == "invalid_or_missing_key_for_core_route"
        for event in captured_events
    )
