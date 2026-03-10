from __future__ import annotations

import pytest

from orket.runtime.operator_override_logging_policy import (
    operator_override_logging_policy_snapshot,
    validate_operator_override_logging_policy,
)


# Layer: unit
def test_operator_override_logging_policy_snapshot_contains_expected_override_types() -> None:
    payload = operator_override_logging_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    override_types = set(payload["override_types"])
    assert "route_override" in override_types
    assert "strictness_override" in override_types


# Layer: contract
def test_validate_operator_override_logging_policy_accepts_current_snapshot() -> None:
    override_types = validate_operator_override_logging_policy()
    assert "route_override" in override_types


# Layer: contract
def test_validate_operator_override_logging_policy_rejects_type_mismatch() -> None:
    payload = operator_override_logging_policy_snapshot()
    payload["override_types"] = [token for token in payload["override_types"] if token != "route_override"]
    with pytest.raises(ValueError, match="E_OPERATOR_OVERRIDE_LOGGING_TYPES_MISMATCH"):
        _ = validate_operator_override_logging_policy(payload)
