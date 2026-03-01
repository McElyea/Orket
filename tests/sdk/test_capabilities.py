from __future__ import annotations

import pytest

from orket_extension_sdk.audio import AudioClip, NullAudioPlayer, NullTTSProvider
from orket_extension_sdk.capabilities import CapabilityRegistry, validate_capabilities


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
    clip = registry.tts().synthesize(text="hello", voice_id="null")
    assert isinstance(clip, AudioClip)
    registry.audio_player().play(clip, blocking=False)
    registry.speech_player().stop()


def test_preflight_rejects_invalid_typed_provider() -> None:
    registry = CapabilityRegistry()
    registry.register("tts.speak", object())
    with pytest.raises(ValueError, match="E_SDK_CAPABILITY_PROVIDER_INVALID"):
        registry.preflight(["tts.speak"])
