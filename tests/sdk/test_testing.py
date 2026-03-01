from __future__ import annotations

import pytest

from orket_extension_sdk.testing import DeterminismHarness, FakeCapabilities, GoldenArtifact, sha256_digest


def test_golden_artifact_digest_stable_for_key_order() -> None:
    a = GoldenArtifact(name="x", payload={"b": 2, "a": 1})
    b = GoldenArtifact(name="x", payload={"a": 1, "b": 2})

    assert a.digest_sha256 == b.digest_sha256


def test_fake_capabilities_registers_sorted() -> None:
    registry = FakeCapabilities.from_mapping({"b": 2, "a": 1})

    assert registry.get("a") == 1
    assert registry.get("b") == 2


def test_determinism_harness_passes_repeatable_output() -> None:
    harness = DeterminismHarness()

    digest = harness.assert_repeatable(lambda: {"x": [1, 2, 3]})

    assert digest == sha256_digest({"x": [1, 2, 3]})


def test_determinism_harness_fails_non_repeatable_output() -> None:
    harness = DeterminismHarness()
    state = {"n": 0}

    def producer() -> dict[str, int]:
        state["n"] += 1
        return {"n": state["n"]}

    with pytest.raises(AssertionError, match="E_SDK_DETERMINISM_MISMATCH"):
        harness.assert_repeatable(producer)
