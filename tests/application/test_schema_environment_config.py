from __future__ import annotations

import pytest

from orket.schema import (
    EnvironmentConfig,
    validate_authoritative_environment_config_payload,
)


def test_environment_config_warns_and_drops_unknown_keys_at_compatibility_boundary() -> None:
    """Layer: contract. Verifies non-authoritative EnvironmentConfig construction stays compatibility-scoped."""
    with pytest.warns(UserWarning, match="ignored unknown key"):
        config = EnvironmentConfig(name="dev", model="test-model", legacy_key="ignored")

    assert not hasattr(config, "legacy_key")


def test_authoritative_environment_config_validation_rejects_unknown_keys() -> None:
    """Layer: contract. Verifies authoritative runtime environment validation fails closed on unknown keys."""
    with pytest.raises(ValueError, match="E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS:legacy_key"):
        validate_authoritative_environment_config_payload(
            {"name": "dev", "model": "test-model", "legacy_key": "ignored"}
        )
