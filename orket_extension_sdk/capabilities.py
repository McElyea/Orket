from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

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

    def preflight(self, required_capabilities: list[CapabilityId]) -> list[CapabilityId]:
        missing = [cap for cap in required_capabilities if cap not in self._providers]
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
