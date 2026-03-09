from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .audio import AudioPlayer, TTSProvider
from .llm import LLMProvider
from .memory import MemoryProvider
from .tui import ScreenRenderer
from .voice import STTProvider, VoiceTurnController

CapabilityId = str


_CAPABILITY_VOCAB: dict[str, dict[str, Any]] = {
    "workspace.root": {"deterministic": True},
    "artifact.root": {"deterministic": True},
    "time.now": {"deterministic": False},
    "rng": {"deterministic": True},
    "model.generate": {"deterministic": False},
    "memory.write": {"deterministic": False},
    "memory.query": {"deterministic": False},
    "audio.play": {"deterministic": False},
    "tts.speak": {"deterministic": False},
    "speech.transcribe": {"deterministic": False},
    "voice.turn_control": {"deterministic": False},
    "speech.play_clip": {"deterministic": False},
    "screen.render": {"deterministic": True},
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

    def llm(self) -> LLMProvider:
        provider = self.get("model.generate")
        if not isinstance(provider, LLMProvider):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: model.generate -> LLMProvider")
        return provider

    def memory_writer(self) -> MemoryProvider:
        provider = self.get("memory.write")
        if not isinstance(provider, MemoryProvider):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: memory.write -> MemoryProvider")
        return provider

    def memory_query(self) -> MemoryProvider:
        provider = self.get("memory.query")
        if not isinstance(provider, MemoryProvider):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: memory.query -> MemoryProvider")
        return provider

    def stt(self) -> STTProvider:
        provider = self.get("speech.transcribe")
        if not isinstance(provider, STTProvider):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: speech.transcribe -> STTProvider")
        return provider

    def voice_turn_controller(self) -> VoiceTurnController:
        provider = self.get("voice.turn_control")
        if not isinstance(provider, VoiceTurnController):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: voice.turn_control -> VoiceTurnController")
        return provider

    def screen(self) -> ScreenRenderer:
        provider = self.get("screen.render")
        if not isinstance(provider, ScreenRenderer):
            raise ValueError("E_SDK_CAPABILITY_PROVIDER_INVALID: screen.render -> ScreenRenderer")
        return provider

    def preflight(self, required_capabilities: list[CapabilityId]) -> list[CapabilityId]:
        missing = [cap for cap in required_capabilities if cap not in self._providers]
        expected: dict[str, type[Any]] = {
            "tts.speak": TTSProvider,
            "audio.play": AudioPlayer,
            "speech.play_clip": AudioPlayer,
            "model.generate": LLMProvider,
            "memory.write": MemoryProvider,
            "memory.query": MemoryProvider,
            "speech.transcribe": STTProvider,
            "voice.turn_control": VoiceTurnController,
            "screen.render": ScreenRenderer,
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
