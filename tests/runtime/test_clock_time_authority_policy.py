from __future__ import annotations

import pytest

from orket.runtime.clock_time_authority_policy import (
    clock_time_authority_policy_snapshot,
    validate_clock_time_authority_policy,
)


# Layer: unit
def test_clock_time_authority_policy_snapshot_contains_expected_defaults() -> None:
    payload = clock_time_authority_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["defaults"]["timezone"] == "UTC"
    assert payload["defaults"]["clock_mode"] == "wall"
    assert payload["allowed_values"]["network_mode"] == ["allowlist", "off"]


# Layer: contract
def test_validate_clock_time_authority_policy_accepts_current_snapshot() -> None:
    payload = validate_clock_time_authority_policy()
    assert payload["unknown_value_behavior"]["network_mode"] == "fail_closed_error"


# Layer: contract
def test_validate_clock_time_authority_policy_rejects_invalid_default() -> None:
    payload = clock_time_authority_policy_snapshot()
    payload["defaults"]["network_mode"] = "internet"
    with pytest.raises(ValueError, match="E_CLOCK_TIME_AUTHORITY_POLICY_INVALID:network_mode_default_not_allowed"):
        _ = validate_clock_time_authority_policy(payload)
