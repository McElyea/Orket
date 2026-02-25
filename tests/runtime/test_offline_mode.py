from __future__ import annotations

import pytest

from orket.runtime.offline_mode import (
    OfflineModeError,
    assert_default_offline_surface,
    command_offline_capability,
    resolve_network_mode,
)


def test_resolve_network_mode_defaults_offline() -> None:
    assert resolve_network_mode() == "offline"


def test_resolve_network_mode_rejects_unknown_value() -> None:
    with pytest.raises(OfflineModeError) as exc:
        resolve_network_mode("invalid-mode")
    assert exc.value.code == "E_NETWORK_MODE_INVALID"


def test_default_offline_surface_requires_core_v1_commands() -> None:
    assert_default_offline_surface(["init", "api_add", "refactor"])


def test_command_offline_capability_unknown_raises() -> None:
    with pytest.raises(OfflineModeError) as exc:
        command_offline_capability("unknown")
    assert exc.value.code == "E_OFFLINE_COMMAND_UNKNOWN"
