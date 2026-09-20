from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.schema import (
    EnvironmentConfig,
    validate_authoritative_environment_config_payload,
)


@pytest.mark.contract
def test_environment_config_rejects_unknown_keys_at_direct_boundary() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EnvironmentConfig(name="dev", model="test-model", legacy_key="ignored")


def test_authoritative_environment_config_validation_rejects_unknown_keys() -> None:
    """Layer: contract. Verifies authoritative runtime environment validation fails closed on unknown keys."""
    with pytest.raises(ValueError, match="E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS:legacy_key"):
        validate_authoritative_environment_config_payload(
            {"name": "dev", "model": "test-model", "legacy_key": "ignored"}
        )
