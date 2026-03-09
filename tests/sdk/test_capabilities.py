from __future__ import annotations

import pytest

from orket_extension_sdk.audio import AudioClip, NullAudioPlayer, NullTTSProvider
from orket_extension_sdk.capabilities import CapabilityRegistry, validate_capabilities
from orket_extension_sdk.llm import GenerateRequest, NullLLMProvider
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest, NullMemoryProvider
from orket_extension_sdk.voice import (
    NullSTTProvider,
    NullVoiceTurnController,
    TranscribeRequest,
    VoiceTurnControlRequest,
)


class _Provider:
    capability_id = "trace.emit"

    def provide(self) -> object:
        return {"enabled": True}


def test_registry_register_and_get() -> None:
    registry = CapabilityRegistry()
    registry.register("fs.read", object())

    assert registry.has("fs.read") is True
    assert registry.get("fs.read") is not None


def test_registry_duplicate_rejected() -> None:
    registry = CapabilityRegistry()
    registry.register("fs.read", object())

    with pytest.raises(ValueError, match="E_SDK_CAPABILITY_DUPLICATE"):
        registry.register("fs.read", object())


def test_registry_preflight_sorted_unique() -> None:
    registry = CapabilityRegistry()
    registry.register("a", object())

    missing = registry.preflight(["z", "b", "z"])

    assert missing == ["b", "z"]


def test_registry_register_provider() -> None:
    registry = CapabilityRegistry()
    registry.register_provider(_Provider())

    assert registry.has("trace.emit") is True


def test_validate_capabilities_warns_by_default() -> None:
    errors, warnings = validate_capabilities(["unknown.cap"], strict=False)
    assert errors == []
    assert warnings == ["E_SDK_CAPABILITY_UNKNOWN: unknown.cap"]


def test_validate_capabilities_errors_in_strict_mode() -> None:
    errors, warnings = validate_capabilities(["unknown.cap"], strict=True)
    assert warnings == []
    assert errors == ["E_SDK_CAPABILITY_UNKNOWN: unknown.cap"]


def test_registry_typed_accessors() -> None:
    registry = CapabilityRegistry()
    registry.register("tts.speak", NullTTSProvider())
    registry.register("audio.play", NullAudioPlayer())
    registry.register("speech.play_clip", NullAudioPlayer())
    registry.register("model.generate", NullLLMProvider())
    registry.register("memory.write", NullMemoryProvider())
    registry.register("memory.query", NullMemoryProvider())
    registry.register("speech.transcribe", NullSTTProvider())
    registry.register("voice.turn_control", NullVoiceTurnController())

    clip = registry.tts().synthesize(text="hello", voice_id="null")
    assert isinstance(clip, AudioClip)
    registry.audio_player().play(clip, blocking=False)
    registry.speech_player().stop()

    llm_result = registry.llm().generate(GenerateRequest(system_prompt="system", user_message="hello"))
    assert llm_result.text == ""

    memory_write = registry.memory_writer().write(
        MemoryWriteRequest(scope="session_memory", key="k", value="v", session_id="s1")
    )
    assert memory_write.ok is False

    memory_query = registry.memory_query().query(
        MemoryQueryRequest(scope="session_memory", query="k", session_id="s1")
    )
    assert memory_query.ok is False

    stt_result = registry.stt().transcribe(TranscribeRequest(audio_bytes=b"pcm"))
    assert stt_result.ok is False

    voice_result = registry.voice_turn_controller().control(VoiceTurnControlRequest(command="start"))
    assert voice_result.ok is False


def test_preflight_rejects_invalid_typed_provider() -> None:
    registry = CapabilityRegistry()
    registry.register("tts.speak", object())
    with pytest.raises(ValueError, match="E_SDK_CAPABILITY_PROVIDER_INVALID"):
        registry.preflight(["tts.speak"])
