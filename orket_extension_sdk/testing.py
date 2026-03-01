from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from .capabilities import CapabilityRegistry


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(slots=True)
class GoldenArtifact:
    name: str
    payload: Any

    @property
    def digest_sha256(self) -> str:
        return sha256_digest(self.payload)


class FakeCapabilities(CapabilityRegistry):
    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> "FakeCapabilities":
        registry = cls()
        for capability_id in sorted(mapping.keys()):
            registry.register(capability_id, mapping[capability_id])
        return registry


class DeterminismHarness:
    def assert_repeatable(self, producer: Callable[[], Any]) -> str:
        first = producer()
        second = producer()
        first_digest = sha256_digest(first)
        second_digest = sha256_digest(second)
        if first_digest != second_digest:
            raise AssertionError(
                f"E_SDK_DETERMINISM_MISMATCH: {first_digest} != {second_digest}"
            )
        return first_digest
