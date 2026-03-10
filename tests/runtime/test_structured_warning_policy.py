from __future__ import annotations

import pytest

from orket.runtime.structured_warning_policy import (
    structured_warning_policy_snapshot,
    validate_structured_warning_policy,
)


# Layer: unit
def test_structured_warning_policy_snapshot_contains_warning_codes() -> None:
    payload = structured_warning_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    codes = {row["warning_code"] for row in payload["warnings"]}
    assert "W_RUNTIME_TRUTH_DRIFT_DETECTED" in codes
    assert "W_ENV_PARITY_MISMATCH" in codes


# Layer: contract
def test_validate_structured_warning_policy_accepts_current_snapshot() -> None:
    warning_codes = validate_structured_warning_policy()
    assert "W_PROVIDER_QUARANTINED" in warning_codes


# Layer: contract
def test_validate_structured_warning_policy_rejects_invalid_severity() -> None:
    payload = structured_warning_policy_snapshot()
    payload["warnings"][0]["severity"] = "urgent"
    with pytest.raises(ValueError, match="E_WARNING_POLICY_SEVERITY_INVALID:W_RUNTIME_TRUTH_DRIFT_DETECTED"):
        _ = validate_structured_warning_policy(payload)
