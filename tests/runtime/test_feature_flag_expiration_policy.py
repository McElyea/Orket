from __future__ import annotations

import pytest

from orket.runtime.feature_flag_expiration_policy import (
    feature_flag_expiration_policy_snapshot,
    validate_feature_flag_expiration_policy,
)


# Layer: unit
def test_feature_flag_expiration_policy_snapshot_contains_expected_fields() -> None:
    payload = feature_flag_expiration_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    required_fields = set(payload["required_fields"])
    assert required_fields == {
        "flag_name",
        "owner",
        "created_at",
        "expires_at",
        "removal_issue",
    }


# Layer: contract
def test_validate_feature_flag_expiration_policy_accepts_current_snapshot() -> None:
    required_fields = validate_feature_flag_expiration_policy()
    assert "flag_name" in required_fields


# Layer: contract
def test_validate_feature_flag_expiration_policy_rejects_required_field_mismatch() -> None:
    payload = feature_flag_expiration_policy_snapshot()
    payload["required_fields"] = [field for field in payload["required_fields"] if field != "flag_name"]
    with pytest.raises(ValueError, match="E_FEATURE_FLAG_EXPIRATION_REQUIRED_FIELDS_MISMATCH"):
        _ = validate_feature_flag_expiration_policy(payload)
