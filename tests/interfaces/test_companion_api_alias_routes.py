from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

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
