from __future__ import annotations

import base64
from pathlib import Path

import pytest

import orket.application.services.extension_runtime_service as extension_runtime_service
from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
from orket.services.scoped_memory_store import ScopedMemoryStore
from orket_extension_sdk.audio import AudioClip, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse
from orket_extension_sdk.voice import TranscribeResponse


class _FakeModelProvider:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(text=f"echo:{request.user_message}", model="fake-local", latency_ms=7)

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
        return AudioClip(sample_rate=16000, channels=1, samples=b"\x01\x02", format="pcm_s16le")


@pytest.mark.asyncio
async def test_extension_runtime_service_namespaces_profile_and_session_memory(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile/session memory records stay isolated per extension id and session id."""
    store = ScopedMemoryStore(tmp_path / "extension_runtime.db")
    service = ExtensionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        memory_store=store,
    )

    await service.memory_write(
        extension_id="orket.companion",
        scope="profile_memory",
        key="companion_setting.config_json",
        value='{"mode":{"role_id":"tutor"}}',
        metadata={"kind": "companion_config_profile_defaults"},
    )
    await service.memory_write(
        extension_id="orket.other",
        scope="profile_memory",
        key="companion_setting.config_json",
        value='{"mode":{"role_id":"researcher"}}',
        metadata={"kind": "companion_config_profile_defaults"},
    )
    await service.memory_write(
        extension_id="orket.companion",
        scope="session_memory",
        session_id="session-a",
        key="turn.000001.user",
        value="hello",
        metadata={"kind": "chat_input"},
    )

    companion_profile = await service.memory_query(
        extension_id="orket.companion",
        scope="profile_memory",
        query="",
        limit=10,
    )
    companion_session = await service.memory_query(
        extension_id="orket.companion",
        scope="session_memory",
        session_id="session-a",
        query="",
        limit=10,
    )
    other_profile = await service.memory_query(
        extension_id="orket.other",
        scope="profile_memory",
        query="",
        limit=10,
    )

    assert [row["key"] for row in companion_profile["records"]] == ["companion_setting.config_json"]
    assert companion_session["records"][0]["key"] == "turn.000001.user"
    assert other_profile["records"][0]["value"] == '{"mode":{"role_id":"researcher"}}'


@pytest.mark.asyncio
async def test_extension_runtime_service_voice_and_transcribe_paths(tmp_path: Path) -> None:
    """Layer: integration. Verifies generic voice state/control, STT, and TTS flows stay truthful."""
    stt = HostSTTCapabilityProvider(transcriber=lambda req: TranscribeResponse(ok=True, text=f"len={len(req.audio_bytes)}"))
    service = ExtensionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        stt_provider=stt,
        tts_provider=_FakeTTSProvider(),  # type: ignore[arg-type]
    )

    state_idle = await service.voice_state(extension_id="orket.companion")
    started = await service.voice_control(extension_id="orket.companion", command="start")
    submitted = await service.voice_control(extension_id="orket.companion", command="submit")
    transcript = await service.transcribe(
        extension_id="orket.companion",
        audio_b64="YQ==",
        mime_type="audio/wav",
    )
    voices = await service.tts_voices(extension_id="orket.companion")
    synth = await service.synthesize(extension_id="orket.companion", text="hello there")

    assert state_idle["state"] == "idle"
    assert started["state"] == "listening"
    assert submitted["state"] == "processing"
    assert transcript["text"] == "len=1"
    assert voices["tts_available"] is True
    assert voices["voices"][0]["voice_id"] == "test_voice"
    assert base64.b64decode(synth["audio_b64"].encode("utf-8"), validate=True) == b"\x01\x02"


@pytest.mark.asyncio
async def test_extension_runtime_service_list_models_and_override_generation(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies model catalog output and provider/model override generation stay available on the generic seam."""

    async def fake_list_provider_models(*, provider: str, base_url, timeout_s: float, api_key):
        del base_url, timeout_s, api_key
        return {
            "requested_provider": provider,
            "canonical_provider": provider,
            "base_url": "http://127.0.0.1:11434",
            "models": ["Command-R:35B", "qwen2.5-coder:7b"],
        }

    monkeypatch.setattr(extension_runtime_service, "list_provider_models", fake_list_provider_models)
    service = ExtensionRuntimeService(project_root=tmp_path, model_provider=_FakeModelProvider())  # type: ignore[arg-type]

    catalog = await service.list_models(extension_id="orket.companion", provider="ollama")
    generated = await service.llm_generate(
        extension_id="orket.companion",
        system_prompt="You are a tester.",
        user_message="hello",
        max_tokens=64,
        temperature=0.2,
        stop_sequences=[],
        provider="lmstudio",
        model="qwen2.5-coder:14b",
    )

    assert catalog["default_model"] == "Command-R:35B"
    assert catalog["models"] == ["Command-R:35B", "qwen2.5-coder:7b"]
    assert generated["text"] == "echo:hello"
