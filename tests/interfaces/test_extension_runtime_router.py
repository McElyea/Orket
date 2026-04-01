from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
from orket.interfaces.routers.extension_runtime import build_extension_runtime_router
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
def extension_runtime_client(tmp_path: Path) -> TestClient:
    service = ExtensionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        stt_provider=HostSTTCapabilityProvider(
            transcriber=lambda req: TranscribeResponse(ok=True, text=f"len={len(req.audio_bytes)}")
        ),
        tts_provider=_FakeTTSProvider(),  # type: ignore[arg-type]
    )
    app = FastAPI()
    app.include_router(build_extension_runtime_router(service_getter=lambda: service), prefix="/v1")
    return TestClient(app)


def test_extension_runtime_router_llm_memory_and_voice_flow(extension_runtime_client: TestClient) -> None:
    """Layer: integration. Verifies generic generate, memory, and voice routes round-trip through the router contract."""
    generate = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/llm/generate",
        json={"system_prompt": "You are a tester.", "user_message": "hello"},
    )
    write = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/memory/write",
        json={
            "scope": "session_memory",
            "session_id": "router-session",
            "key": "turn.000001.user",
            "value": "hello",
            "metadata": {"kind": "chat_input"},
        },
    )
    query = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/memory/query",
        json={"scope": "session_memory", "session_id": "router-session", "query": "", "limit": 10},
    )
    start = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/voice/control",
        json={"command": "start"},
    )
    state = extension_runtime_client.get("/v1/extensions/orket.companion/runtime/voice/state")
    transcribe = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/voice/transcribe",
        json={"audio_b64": "YWI=", "mime_type": "audio/wav"},
    )
    synthesize = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/tts/synthesize",
        json={"text": "hello there"},
    )

    assert generate.status_code == 200
    assert generate.json()["text"] == "echo:hello"
    assert write.status_code == 200
    assert query.json()["records"][0]["key"] == "turn.000001.user"
    assert start.json()["state"] == "listening"
    assert state.json()["state"] == "listening"
    assert transcribe.json()["text"] == "len=2"
    assert base64.b64decode(synthesize.json()["audio_b64"].encode("utf-8"), validate=True) == b"\xAA\xBB"


def test_extension_runtime_router_invalid_scope_returns_error_envelope(extension_runtime_client: TestClient) -> None:
    """Layer: contract. Verifies invalid memory scopes fail closed with structured error envelopes."""
    response = extension_runtime_client.post(
        "/v1/extensions/orket.companion/runtime/memory/query",
        json={"scope": "invalid", "query": "", "limit": 10},
    )
    assert response.status_code == 422


def test_extension_runtime_router_models_failure_returns_truthful_degraded_error() -> None:
    """Layer: contract. Verifies model-catalog failures stay degraded and explicit on the generic extension seam."""

    class _FailingService:
        async def list_models(self, *, extension_id: str, provider: str) -> dict[str, object]:
            del extension_id
            raise RuntimeError(f"catalog unavailable:{provider}")

    app = FastAPI()
    app.include_router(build_extension_runtime_router(service_getter=lambda: _FailingService()), prefix="/v1")
    client = TestClient(app)

    response = client.get("/v1/extensions/orket.companion/runtime/models", params={"provider": "ollama"})

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["ok"] is False
    assert detail["degraded"] is True
    assert detail["code"] == "E_EXTENSION_RUNTIME_MODEL_CATALOG_UNAVAILABLE"
    assert detail["requested_provider"] == "ollama"
