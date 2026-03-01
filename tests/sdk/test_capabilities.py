from __future__ import annotations

import pytest

from orket_extension_sdk.capabilities import CapabilityRegistry


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
