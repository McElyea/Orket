"""Immutable observed inputs for architecture policy and settings evaluation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


def freeze_policy_environment(environment: Mapping[str, str]) -> Mapping[str, str]:
    observed = dict(environment)
    if any(type(key) is not str or type(value) is not str for key, value in observed.items()):
        raise TypeError("E_RUNTIME_POLICY_ENVIRONMENT_STRINGS_REQUIRED")
    return MappingProxyType(observed)


@dataclass(frozen=True)
class ArchitecturePolicySnapshot:
    microservices_unlocked: bool

    def __post_init__(self) -> None:
        if type(self.microservices_unlocked) is not bool:
            raise TypeError("E_ARCHITECTURE_POLICY_BOOLEAN_REQUIRED")


@dataclass(frozen=True)
class RuntimePolicySnapshot:
    architecture: ArchitecturePolicySnapshot
    microservices_pilot_stable: bool
    environment: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.architecture, ArchitecturePolicySnapshot):
            raise TypeError("E_ARCHITECTURE_POLICY_SNAPSHOT_REQUIRED")
        if type(self.microservices_pilot_stable) is not bool:
            raise TypeError("E_PILOT_STABILITY_BOOLEAN_REQUIRED")
        object.__setattr__(self, "environment", freeze_policy_environment(self.environment))
