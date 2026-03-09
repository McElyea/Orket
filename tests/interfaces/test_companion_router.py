from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
from orket.interfaces.routers.companion import build_companion_router
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse
from orket_extension_sdk.voice import TranscribeResponse


class _FakeModelProvider:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(text=f"echo:{request.user_message}", model="fake", latency_ms=5)

    def is_available(self) -> bool:
        return True


@pytest.fixture
def companion_client(tmp_path: Path) -> TestClient:
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        stt_provider=HostSTTCapabilityProvider(
            transcriber=lambda req: TranscribeResponse(ok=True, text=f"len={len(req.audio_bytes)}")
        ),
    )
    app = FastAPI()
    app.include_router(build_companion_router(service_getter=lambda: service), prefix="/v1")
    return TestClient(app)


def test_companion_router_chat_config_and_history_flow(companion_client: TestClient) -> None:
    """Layer: integration. Verifies config update, chat, and history endpoints through router contract."""
    update = companion_client.patch(
        "/v1/companion/config",
        json={
            "session_id": "router-session",
            "scope": "next_turn",
            "patch": {"mode": {"role_id": "tutor"}},
        },
    )
    assert update.status_code == 200
    assert update.json()["config"]["mode"]["role_id"] == "tutor"

    chat = companion_client.post(
        "/v1/companion/chat",
        json={"session_id": "router-session", "message": "hello"},
    )
    assert chat.status_code == 200
    payload = chat.json()
    assert payload["message"] == "echo:hello"
    assert payload["config"]["mode"]["role_id"] == "tutor"

    history = companion_client.get("/v1/companion/history", params={"session_id": "router-session"})
    assert history.status_code == 200
    rows = history.json()["history"]
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"


def test_companion_router_voice_and_transcribe_flow(companion_client: TestClient) -> None:
    """Layer: integration. Verifies voice control/state and transcribe endpoints."""
    start = companion_client.post("/v1/companion/voice/control", json={"command": "start"})
    assert start.status_code == 200
    assert start.json()["state"] == "listening"

    state = companion_client.get("/v1/companion/voice/state")
    assert state.status_code == 200
    assert state.json()["state"] == "listening"

    transcribe = companion_client.post(
        "/v1/companion/voice/transcribe",
        json={"audio_b64": "YWI=", "mime_type": "audio/wav"},
    )
    assert transcribe.status_code == 200
    assert transcribe.json()["text"] == "len=2"


def test_companion_router_invalid_config_patch_returns_error_envelope(companion_client: TestClient) -> None:
    """Layer: contract. Verifies router error responses return structured error envelopes."""
    response = companion_client.patch(
        "/v1/companion/config",
        json={
            "session_id": "router-session",
            "scope": "next_turn",
            "patch": {"invalid": {"value": True}},
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["ok"] is False
    assert detail["code"] == "E_COMPANION_CONFIG_SECTION_INVALID"
