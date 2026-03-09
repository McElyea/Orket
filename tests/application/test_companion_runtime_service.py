from __future__ import annotations

import base64
from pathlib import Path

import pytest

import orket.application.services.companion_runtime_service as companion_runtime_service
from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
from orket_extension_sdk.audio import AudioClip, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse
from orket_extension_sdk.voice import TranscribeResponse


class _FakeModelProvider:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            text=f"echo:{request.user_message}",
            model="fake-local",
            latency_ms=7,
        )

    def is_available(self) -> bool:
        return True


class _FailingModelProvider:
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        del request
        raise RuntimeError("model backend offline")

    def is_available(self) -> bool:
        return False


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
async def test_companion_runtime_service_chat_consumes_pending_next_turn_mode(tmp_path: Path) -> None:
    """Layer: integration. Verifies next-turn mode updates apply on one chat turn and then clear."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    await service.update_config(
        session_id="s1",
        scope="next_turn",
        patch={"mode": {"role_id": "tutor"}},
    )
    preview = await service.get_config(session_id="s1")
    assert preview.mode.role_id.value == "tutor"

    result = await service.chat(session_id="s1", message="hello")
    assert result["message"] == "echo:hello"
    assert result["config"]["mode"]["role_id"] == "tutor"

    after = await service.get_config(session_id="s1")
    assert after.mode.role_id.value == "general_assistant"


@pytest.mark.asyncio
async def test_companion_runtime_service_profile_config_persists_across_sessions(tmp_path: Path) -> None:
    """Layer: integration. Verifies profile-scope config writes persist and seed new sessions."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    await service.update_config(
        session_id="primary",
        scope="profile",
        patch={"memory": {"profile_memory_enabled": False}},
    )
    first = await service.get_config(session_id="primary")
    second = await service.get_config(session_id="secondary")
    assert first.memory.profile_memory_enabled is False
    assert second.memory.profile_memory_enabled is False

    service_reloaded = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    third = await service_reloaded.get_config(session_id="reloaded")
    assert third.memory.profile_memory_enabled is False


@pytest.mark.asyncio
async def test_companion_runtime_service_clear_session_resets_history_and_memory(tmp_path: Path) -> None:
    """Layer: integration. Verifies clear-session operation resets in-memory history and deletes session records."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    await service.update_config(
        session_id="s-clear",
        scope="session",
        patch={"memory": {"episodic_memory_enabled": True}},
    )
    await service.chat(session_id="s-clear", message="first")
    history_before = await service.get_history(session_id="s-clear", limit=20)
    assert len(history_before) == 2

    cleared = await service.clear_session_memory(session_id="s-clear")
    assert cleared["ok"] is True
    assert cleared["deleted_records"] >= 3
    assert cleared["deleted_episodic_records"] >= 1
    history_after = await service.get_history(session_id="s-clear", limit=20)
    assert history_after == []


@pytest.mark.asyncio
async def test_companion_runtime_service_voice_and_transcribe_paths(tmp_path: Path) -> None:
    """Layer: integration. Verifies voice state/control flows and STT transcribe wiring."""
    stt = HostSTTCapabilityProvider(transcriber=lambda req: TranscribeResponse(ok=True, text=f"len={len(req.audio_bytes)}"))
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
        stt_provider=stt,
        tts_provider=_FakeTTSProvider(),  # type: ignore[arg-type]
    )
    state_idle = await service.voice_state()
    assert state_idle["state"] == "idle"

    started = await service.voice_control(command="start")
    assert started.ok is True
    assert started.state == "listening"

    submitted = await service.voice_control(command="submit")
    assert submitted.ok is True
    assert submitted.state == "processing"
    state_after_submit = await service.voice_state()
    assert state_after_submit["state"] == "idle"

    transcript = await service.transcribe(audio_b64="YQ==", mime_type="audio/wav")
    assert transcript.ok is True
    assert transcript.text == "len=1"

    voices = await service.tts_voices()
    assert voices["ok"] is True
    assert voices["tts_available"] is True
    assert voices["default_voice_id"] == "test_voice"
    assert voices["voices"][0]["voice_id"] == "test_voice"

    cadence_manual = await service.suggest_voice_cadence(session_id="default", text="short text")
    assert cadence_manual["adaptive_cadence_enabled"] is False
    assert cadence_manual["source"] == "manual"

    synth = await service.synthesize(text="hello there")
    assert synth["ok"] is True
    assert synth["sample_rate"] == 16000
    assert base64.b64decode(synth["audio_b64"].encode("utf-8"), validate=True) == b"\x01\x02"

    await service.update_config(
        session_id="default",
        scope="session",
        patch={
            "voice": {
                "adaptive_cadence_enabled": True,
                "adaptive_cadence_min_sec": 0.5,
                "adaptive_cadence_max_sec": 3.0,
            }
        },
    )
    cadence_adaptive = await service.suggest_voice_cadence(
        session_id="default",
        text="this is a longer utterance to drive adaptive cadence",
    )
    assert cadence_adaptive["adaptive_cadence_enabled"] is True
    assert cadence_adaptive["source"] == "adaptive"
    assert 0.5 <= cadence_adaptive["suggested_silence_delay_sec"] <= 3.0

    with pytest.raises(ValueError, match="E_COMPANION_AUDIO_B64_INVALID"):
        await service.transcribe(audio_b64="invalid$$$", mime_type="audio/wav")


@pytest.mark.asyncio
async def test_companion_runtime_service_synthesize_degrades_when_tts_unavailable(tmp_path: Path) -> None:
    """Layer: integration. Verifies synthesize returns explicit unavailable response when no TTS backend is configured."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    voices = await service.tts_voices()
    assert voices["tts_available"] is False
    assert voices["voices"] == []
    synth = await service.synthesize(text="hello")
    assert synth["ok"] is False
    assert synth["error_code"] == "tts_unavailable"
    assert synth["audio_b64"] == ""


@pytest.mark.asyncio
async def test_companion_runtime_service_rejects_empty_cadence_text(tmp_path: Path) -> None:
    """Layer: integration. Verifies adaptive cadence suggestion fails closed when text seed is empty."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FakeModelProvider(),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="E_COMPANION_CADENCE_TEXT_REQUIRED"):
        await service.suggest_voice_cadence(session_id="s-cadence", text="   ")


@pytest.mark.asyncio
async def test_companion_runtime_service_chat_surfaces_generation_failures_with_code(tmp_path: Path) -> None:
    """Layer: integration. Verifies model generation failures produce explicit Companion error codes."""
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FailingModelProvider(),  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="E_COMPANION_MODEL_GENERATION_FAILED"):
        await service.chat(session_id="s-fail", message="hello")


@pytest.mark.asyncio
async def test_companion_runtime_service_chat_uses_provider_override_path(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies provider/model overrides route through the override generation path."""
    captured: dict[str, str] = {}

    def fake_generate_with_overrides(request: GenerateRequest, provider_override: str, model_override: str) -> GenerateResponse:
        captured["provider"] = provider_override
        captured["model"] = model_override
        return GenerateResponse(text=f"override:{request.user_message}", model="override-model", latency_ms=3)

    monkeypatch.setattr(companion_runtime_service, "generate_with_provider_overrides", fake_generate_with_overrides)
    service = CompanionRuntimeService(
        project_root=tmp_path,
        model_provider=_FailingModelProvider(),  # type: ignore[arg-type]
    )
    result = await service.chat(
        session_id="s-override",
        message="hello",
        provider="lmstudio",
        model="qwen2.5-coder:14b",
    )
    assert result["message"] == "override:hello"
    assert captured == {"provider": "lmstudio", "model": "qwen2.5-coder:14b"}
