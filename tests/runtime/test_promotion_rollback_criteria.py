from __future__ import annotations

import pytest

from orket.runtime.promotion_rollback_criteria import (
    promotion_rollback_criteria_snapshot,
    validate_promotion_rollback_criteria,
)


# Layer: unit
def test_promotion_rollback_criteria_snapshot_contains_expected_triggers() -> None:
    payload = promotion_rollback_criteria_snapshot()
    assert payload["schema_version"] == "1.0"
    triggers = {row["trigger"] for row in payload["triggers"]}
    assert triggers == {
        "acceptance_gate_failure",
        "contract_drift_detected",
        "critical_regression_detected",
    }


# Layer: contract
def test_validate_promotion_rollback_criteria_accepts_current_snapshot() -> None:
    triggers = validate_promotion_rollback_criteria()
    assert "acceptance_gate_failure" in triggers


# Layer: contract
def test_validate_promotion_rollback_criteria_rejects_trigger_set_mismatch() -> None:
    payload = promotion_rollback_criteria_snapshot()
    payload["triggers"] = [row for row in payload["triggers"] if row["trigger"] != "critical_regression_detected"]
    with pytest.raises(ValueError, match="E_PROMOTION_ROLLBACK_CRITERIA_TRIGGER_SET_MISMATCH"):
        _ = validate_promotion_rollback_criteria(payload)
