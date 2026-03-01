from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .audio import AudioPlayer, TTSProvider

CapabilityId = str


_CAPABILITY_VOCAB: dict[str, dict[str, Any]] = {
    "workspace.root": {"deterministic": True},
    "artifact.root": {"deterministic": True},
    "time.now": {"deterministic": False},
    "rng": {"deterministic": True},
    "model.generate": {"deterministic": False},
    "audio.play": {"deterministic": False},
    "tts.speak": {"deterministic": False},
    "speech.play_clip": {"deterministic": False},
}


class CapabilityProvider(Protocol):
    """Provider contract for a named capability."""

    capability_id: CapabilityId

    def provide(self) -> Any:
        ...


@dataclass(slots=True)
class CapabilityRegistry:
    """Deterministic capability registry used by workloads."""

    _providers: dict[CapabilityId, Any]

    def __init__(self) -> None:
        self._providers = {}

    def register(self, capability_id: CapabilityId, provider: Any) -> None:
        if not capability_id:
            raise ValueError("E_SDK_CAPABILITY_INVALID_ID")
        if capability_id in self._providers:
            raise ValueError(f"E_SDK_CAPABILITY_DUPLICATE: {capability_id}")
        self._providers[capability_id] = provider

    def register_provider(self, provider: CapabilityProvider) -> None:
        self.register(provider.capability_id, provider.provide())

    def has(self, capability_id: CapabilityId) -> bool:
        return capability_id in self._providers

    def get(self, capability_id: CapabilityId) -> Any:
        if capability_id not in self._providers:
            raise ValueError(f"E_SDK_CAPABILITY_MISSING: {capability_id}")
        return self._providers[capability_id]

    def tts(self) -> TTSProvider:
        provider = self.get("tts.speak")
        if not isinstance(provider, TTSProvider):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: tts.speak -> TTSProvider")
        return provider

    def audio_player(self) -> AudioPlayer:
        provider = self.get("audio.play")
        if not isinstance(provider, AudioPlayer):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: audio.play -> AudioPlayer")
        return provider

    def speech_player(self) -> AudioPlayer:
        provider = self.get("speech.play_clip")
        if not isinstance(provider, AudioPlayer):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: speech.play_clip -> AudioPlayer")
        return provider

    def preflight(self, required_capabilities: list[CapabilityId]) -> list[CapabilityId]:
        missing = [cap for cap in required_capabilities if cap not in self._providers]
        expected: dict[str, type[Any]] = {
            "tts.speak": TTSProvider,
            "audio.play": AudioPlayer,
            "speech.play_clip": AudioPlayer,
        }
        invalid: list[str] = []
        for capability_id in sorted(set(required_capabilities)):
            if capability_id in missing:
                continue
            provider = self._providers.get(capability_id)
            expected_type = expected.get(capability_id)
            if expected_type is None:
                continue
            if not isinstance(provider, expected_type):
                invalid.append(f"{capability_id} -> {expected_type.__name__}")
        if invalid:
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: " + ", ".join(invalid))
        return sorted(set(missing))


def load_capability_vocab() -> dict[str, dict[str, Any]]:
    return dict(_CAPABILITY_VOCAB)


def validate_capabilities(
    required_capabilities: list[str],
    *,
    strict: bool,
    vocab: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    known = set((vocab or load_capability_vocab()).keys())
    seen: set[str] = set()

    for raw in list(required_capabilities or []):
        capability_id = str(raw or "").strip()
        if not capability_id:
            errors.append("E_SDK_CAPABILITY_INVALID_ID")
            continue
        if capability_id in seen:
            continue
        seen.add(capability_id)
        if capability_id not in known:
            code = f"E_SDK_CAPABILITY_UNKNOWN: {capability_id}"
            if strict:
                errors.append(code)
            else:
                warnings.append(code)

    return errors, warnings
