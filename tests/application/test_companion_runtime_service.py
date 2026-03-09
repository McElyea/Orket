from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.companion_runtime_service import CompanionRuntimeService
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider
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
    await service.chat(session_id="s-clear", message="first")
    history_before = await service.get_history(session_id="s-clear", limit=20)
    assert len(history_before) == 2

    cleared = await service.clear_session_memory(session_id="s-clear")
    assert cleared["ok"] is True
    assert cleared["deleted_records"] >= 2
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

    with pytest.raises(ValueError, match="E_COMPANION_AUDIO_B64_INVALID"):
        await service.transcribe(audio_b64="invalid$$$", mime_type="audio/wav")
