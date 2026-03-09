from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
from orket.interfaces.routers.companion import build_companion_router
from orket_extension_sdk.audio import AudioClip, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse
from orket_extension_sdk.voice import TranscribeResponse


class _FakeModelProvider:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(text=f"echo:{request.user_message}", model="fake", latency_ms=5)

    def is_available(self) -> bool:
        return True


class _FakeTTSProvider:
    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(voice_id="test_voice", display_name="Test Voice", language="en", tags=[])]

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        del text, voice_id, emotion_hint, speed
        return AudioClip(sample_rate=16000, channels=1, samples=b"\xAA\xBB", format="pcm_s16le")


@pytest.fixture
def companion_client(tmp_path: Path) -> TestClient:
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        stt_provider=HostSTTCapabilityProvider(
            transcriber=lambda req: TranscribeResponse(ok=True, text=f"len={len(req.audio_bytes)}")
        ),
        tts_provider=_FakeTTSProvider(),  # type: ignore[arg-type]
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
    """Layer: integration. Verifies voice control/state, transcribe, and synthesize endpoints."""
    start = companion_client.post("/v1/companion/voice/control", json={"command": "start"})
    assert start.status_code == 200
    assert start.json()["state"] == "listening"

    state = companion_client.get("/v1/companion/voice/state")
    assert state.status_code == 200
    assert state.json()["state"] == "listening"

    voices = companion_client.get("/v1/companion/voice/voices")
    assert voices.status_code == 200
    voices_payload = voices.json()
    assert voices_payload["tts_available"] is True
    assert voices_payload["voices"][0]["voice_id"] == "test_voice"

    cadence = companion_client.post(
        "/v1/companion/voice/cadence/suggest",
        json={"session_id": "router-session", "text": "a short voice draft"},
    )
    assert cadence.status_code == 200
    cadence_payload = cadence.json()
    assert cadence_payload["ok"] is True
    assert cadence_payload["source"] == "manual"

    transcribe = companion_client.post(
        "/v1/companion/voice/transcribe",
        json={"audio_b64": "YWI=", "mime_type": "audio/wav"},
    )
    assert transcribe.status_code == 200
    assert transcribe.json()["text"] == "len=2"

    synthesize = companion_client.post(
        "/v1/companion/voice/synthesize",
        json={"text": "hello there"},
    )
    assert synthesize.status_code == 200
    synth_payload = synthesize.json()
    assert synth_payload["ok"] is True
    assert synth_payload["sample_rate"] == 16000
    assert base64.b64decode(synth_payload["audio_b64"].encode("utf-8"), validate=True) == b"\xAA\xBB"


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
