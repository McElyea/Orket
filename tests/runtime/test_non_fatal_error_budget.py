from __future__ import annotations

import pytest

from orket.runtime.non_fatal_error_budget import (
    non_fatal_error_budget_snapshot,
    validate_non_fatal_error_budget,
)


# Layer: unit
def test_non_fatal_error_budget_snapshot_contains_expected_budget_ids() -> None:
    payload = non_fatal_error_budget_snapshot()
    assert payload["schema_version"] == "1.0"
    budget_ids = {row["budget_id"] for row in payload["budgets"]}
    assert budget_ids == {
        "degraded_completion_ratio",
        "repair_applied_ratio",
        "timeout_recovery_ratio",
        "non_fatal_validation_error_ratio",
    }


# Layer: contract
def test_validate_non_fatal_error_budget_accepts_current_snapshot() -> None:
    budget_ids = validate_non_fatal_error_budget()
    assert "degraded_completion_ratio" in budget_ids


# Layer: contract
def test_validate_non_fatal_error_budget_rejects_budget_set_mismatch() -> None:
    payload = non_fatal_error_budget_snapshot()
    payload["budgets"] = [row for row in payload["budgets"] if row["budget_id"] != "timeout_recovery_ratio"]
    with pytest.raises(ValueError, match="E_NON_FATAL_ERROR_BUDGET_ID_SET_MISMATCH"):
        _ = validate_non_fatal_error_budget(payload)
