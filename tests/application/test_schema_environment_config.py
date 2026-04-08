from __future__ import annotations

import pytest

from orket.schema import EnvironmentConfig


def test_environment_config_ignores_unknown_keys_with_warning() -> None:
    """Layer: contract. Verifies EnvironmentConfig drops unknown keys before the future forbid step."""
    with pytest.warns(UserWarning, match="ignored unknown key"):
        config = EnvironmentConfig(name="dev", model="test-model", legacy_key="ignored")

    assert not hasattr(config, "legacy_key")
