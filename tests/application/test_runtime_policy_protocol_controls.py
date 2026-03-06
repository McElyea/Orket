from __future__ import annotations

import pytest

from orket.application.services.runtime_policy import (
    resolve_local_prompting_allow_fallback,
    resolve_local_prompting_fallback_profile_id,
    resolve_local_prompting_mode,
    resolve_protocol_determinism_controls,
)


def test_resolve_protocol_determinism_controls_defaults() -> None:
    controls = resolve_protocol_determinism_controls()
    assert controls["timezone"] == "UTC"
    assert controls["locale"] == "C.UTF-8"
    assert controls["network_mode"] == "off"
    assert controls["network_allowlist"] == []
    assert controls["clock_mode"] == "wall"
    assert controls["clock_artifact_ref"] == ""
    assert controls["env_allowlist"] == []
    assert isinstance(controls["network_allowlist_hash"], str)
    assert len(controls["network_allowlist_hash"]) == 64
    assert isinstance(controls["clock_artifact_hash"], str)
    assert len(controls["clock_artifact_hash"]) == 64
    assert isinstance(controls["env_allowlist_hash"], str)
    assert len(controls["env_allowlist_hash"]) == 64


def test_resolve_protocol_determinism_controls_uses_first_sources() -> None:
    controls = resolve_protocol_determinism_controls(
        timezone_values=["", "America/Denver"],
        locale_values=["", "en_US.UTF-8"],
        network_mode_values=["", "allowlist"],
        network_allowlist_values=["", "api.example.com,cache.example.com"],
        clock_mode_values=["", "artifact"],
        clock_artifact_ref_values=["", "artifacts/clock/run-a.json"],
        env_allowlist_values=["", "HOME,PATH"],
        environment={"HOME": "/home/user", "PATH": "/bin", "SECRET": "x"},
    )
    assert controls["timezone"] == "America/Denver"
    assert controls["locale"] == "en_US.UTF-8"
    assert controls["network_mode"] == "allowlist"
    assert controls["network_allowlist"] == ["api.example.com", "cache.example.com"]
    assert controls["clock_mode"] == "artifact_replay"
    assert controls["clock_artifact_ref"] == "artifacts/clock/run-a.json"
    assert controls["env_allowlist"] == ["HOME", "PATH"]
    assert controls["env_snapshot"] == {"HOME": "/home/user", "PATH": "/bin"}


def test_resolve_protocol_determinism_controls_rejects_invalid_network_mode() -> None:
    with pytest.raises(ValueError) as exc:
        resolve_protocol_determinism_controls(network_mode_values=["internet"])
    assert "E_NETWORK_MODE_INVALID" in str(exc.value)


def test_resolve_local_prompting_mode_defaults_to_shadow() -> None:
    assert resolve_local_prompting_mode() == "shadow"
    assert resolve_local_prompting_mode("enforce") == "enforce"
    assert resolve_local_prompting_mode("invalid-mode") == "shadow"


def test_resolve_local_prompting_fallback_controls() -> None:
    assert resolve_local_prompting_allow_fallback("enabled") is True
    assert resolve_local_prompting_allow_fallback("disabled") is False
    assert resolve_local_prompting_allow_fallback("invalid") is False
    assert (
        resolve_local_prompting_fallback_profile_id("", "openai_compat.qwen.openai_messages.v1")
        == "openai_compat.qwen.openai_messages.v1"
    )
