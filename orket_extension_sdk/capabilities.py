from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

CapabilityId = str


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
