from __future__ import annotations

import pytest

from orket.application.services.runtime_policy import resolve_protocol_determinism_controls


def test_resolve_protocol_determinism_controls_defaults() -> None:
    controls = resolve_protocol_determinism_controls()
    assert controls["timezone"] == "UTC"
    assert controls["locale"] == "C.UTF-8"
    assert controls["network_mode"] == "off"
    assert controls["env_allowlist"] == []
    assert isinstance(controls["env_allowlist_hash"], str)
    assert len(controls["env_allowlist_hash"]) == 64


def test_resolve_protocol_determinism_controls_uses_first_sources() -> None:
    controls = resolve_protocol_determinism_controls(
        timezone_values=["", "America/Denver"],
        locale_values=["", "en_US.UTF-8"],
        network_mode_values=["", "allowlist"],
        env_allowlist_values=["", "HOME,PATH"],
        environment={"HOME": "/home/user", "PATH": "/bin", "SECRET": "x"},
    )
    assert controls["timezone"] == "America/Denver"
    assert controls["locale"] == "en_US.UTF-8"
    assert controls["network_mode"] == "allowlist"
    assert controls["env_allowlist"] == ["HOME", "PATH"]
    assert controls["env_snapshot"] == {"HOME": "/home/user", "PATH": "/bin"}


def test_resolve_protocol_determinism_controls_rejects_invalid_network_mode() -> None:
    with pytest.raises(ValueError) as exc:
        resolve_protocol_determinism_controls(network_mode_values=["internet"])
    assert "E_NETWORK_MODE_INVALID" in str(exc.value)
