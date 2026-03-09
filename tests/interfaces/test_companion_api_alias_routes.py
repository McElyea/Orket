from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import create_api_app


def test_companion_status_available_under_v1_and_api_v1(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies Companion status endpoint is exposed on both `/v1` and `/api/v1` seams."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}

    v1 = client.get("/v1/companion/status", headers=headers)
    api_v1 = client.get("/api/v1/companion/status", headers=headers)
    assert v1.status_code == 200
    assert api_v1.status_code == 200
    assert v1.json()["ok"] is True
    assert api_v1.json()["ok"] is True


def test_companion_api_config_round_trip(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies Companion config update/read contracts on `/api/v1` seam."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}

    update = client.patch(
        "/api/v1/companion/config",
        headers=headers,
        json={
            "session_id": "api-route-session",
            "scope": "next_turn",
            "patch": {"mode": {"role_id": "tutor"}},
        },
    )
    assert update.status_code == 200
    assert update.json()["config"]["mode"]["role_id"] == "tutor"

    fetched = client.get(
        "/api/v1/companion/config",
        headers=headers,
        params={"session_id": "api-route-session"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["config"]["mode"]["role_id"] == "tutor"


def test_companion_voice_synthesize_available_under_v1_and_api_v1(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies Companion TTS synthesize endpoint is exposed on both `/v1` and `/api/v1` seams."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}

    v1 = client.post("/v1/companion/voice/synthesize", headers=headers, json={"text": "hello world"})
    api_v1 = client.post("/api/v1/companion/voice/synthesize", headers=headers, json={"text": "hello world"})
    assert v1.status_code == 200
    assert api_v1.status_code == 200
    assert "ok" in v1.json()
    assert "ok" in api_v1.json()


def test_companion_voice_voices_available_under_v1_and_api_v1(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies Companion TTS voices endpoint is exposed on both `/v1` and `/api/v1` seams."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}

    v1 = client.get("/v1/companion/voice/voices", headers=headers)
    api_v1 = client.get("/api/v1/companion/voice/voices", headers=headers)
    assert v1.status_code == 200
    assert api_v1.status_code == 200
    assert "voices" in v1.json()
    assert "voices" in api_v1.json()


def test_companion_voice_cadence_suggest_available_under_v1_and_api_v1(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies Companion cadence suggestion endpoint is exposed on both `/v1` and `/api/v1` seams."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    client = TestClient(create_api_app(project_root=tmp_path))
    headers = {"X-API-Key": "test-key"}
    payload = {"session_id": "api-cadence", "text": "hello cadence"}

    v1 = client.post("/v1/companion/voice/cadence/suggest", headers=headers, json=payload)
    api_v1 = client.post("/api/v1/companion/voice/cadence/suggest", headers=headers, json=payload)
    assert v1.status_code == 200
    assert api_v1.status_code == 200
    assert "suggested_silence_delay_sec" in v1.json()
    assert "suggested_silence_delay_sec" in api_v1.json()


def test_companion_scoped_api_key_only_grants_companion_routes(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies companion-scoped key does not authorize non-companion `/v1/*` endpoints."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_COMPANION_API_KEY", "companion-key")
    client = TestClient(create_api_app(project_root=tmp_path))

    companion_headers = {"X-API-Key": "companion-key"}
    core_headers = {"X-API-Key": "core-key"}

    companion_status = client.get("/api/v1/companion/status", headers=companion_headers)
    assert companion_status.status_code == 200
    assert companion_status.json()["ok"] is True

    companion_status_v1 = client.get("/v1/companion/status", headers=companion_headers)
    assert companion_status_v1.status_code == 200
    assert companion_status_v1.json()["ok"] is True

    non_companion_with_companion_key = client.get("/v1/version", headers=companion_headers)
    assert non_companion_with_companion_key.status_code == 403
    assert non_companion_with_companion_key.json()["detail"] == "Could not validate credentials"

    non_companion_with_core_key = client.get("/v1/version", headers=core_headers)
    assert non_companion_with_core_key.status_code == 200


def test_companion_core_key_compatibility_mode_allows_companion_routes(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies default compatibility mode allows the core key on Companion routes."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_COMPANION_API_KEY", "companion-key")
    monkeypatch.delenv("ORKET_COMPANION_KEY_STRICT", raising=False)
    client = TestClient(create_api_app(project_root=tmp_path))

    response = client.get("/api/v1/companion/status", headers={"X-API-Key": "core-key"})
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_companion_strict_mode_rejects_core_key_on_companion_routes(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies strict mode enforces companion-only key usage on Companion routes."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_COMPANION_API_KEY", "companion-key")
    monkeypatch.setenv("ORKET_COMPANION_KEY_STRICT", "true")
    client = TestClient(create_api_app(project_root=tmp_path))

    rejected = client.get("/api/v1/companion/status", headers={"X-API-Key": "core-key"})
    assert rejected.status_code == 403
    assert rejected.json()["detail"] == "Could not validate credentials"

    accepted = client.get("/api/v1/companion/status", headers={"X-API-Key": "companion-key"})
    assert accepted.status_code == 200
    assert accepted.json()["ok"] is True

    core_route = client.get("/v1/version", headers={"X-API-Key": "core-key"})
    assert core_route.status_code == 200


def test_companion_key_rejected_on_core_route_emits_auth_rejection_event(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies scoped key misuse on core routes emits structured auth rejection telemetry."""
    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_COMPANION_API_KEY", "companion-key")
    captured_events: list[dict[str, object]] = []

    def _fake_log_event(name, payload, workspace=None):  # noqa: ANN001
        if name == "api_auth_rejected" and isinstance(payload, dict):
            captured_events.append(payload)

    monkeypatch.setattr(api_module, "log_event", _fake_log_event)
    client = TestClient(create_api_app(project_root=tmp_path))

    response = client.get("/v1/version", headers={"X-API-Key": "companion-key"})
    assert response.status_code == 403

    assert any(
        str(event.get("route_class")) == "core"
        and str(event.get("reason")) == "companion_key_rejected_on_core_route"
        for event in captured_events
    )
