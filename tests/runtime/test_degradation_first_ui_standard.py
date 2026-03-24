from __future__ import annotations

import pytest

from orket.runtime.degradation_first_ui_standard import (
    degradation_first_ui_standard_snapshot,
    validate_degradation_first_ui_standard,
)


# Layer: unit
def test_degradation_first_ui_standard_snapshot_contains_expected_check_ids() -> None:
    payload = degradation_first_ui_standard_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "runtime_status_vocabulary_includes_degraded",
        "ui_state_registry_includes_degraded_state",
        "structured_warning_policy_declares_runtime_degraded",
        "companion_models_unavailable_returns_truthful_degraded_failure",
    }


# Layer: contract
def test_validate_degradation_first_ui_standard_accepts_current_snapshot() -> None:
    check_ids = validate_degradation_first_ui_standard()
    assert "companion_models_unavailable_returns_truthful_degraded_failure" in check_ids


# Layer: contract
def test_validate_degradation_first_ui_standard_rejects_check_set_mismatch() -> None:
    payload = degradation_first_ui_standard_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "runtime_status_vocabulary_includes_degraded"]
    with pytest.raises(ValueError, match="E_DEGRADATION_FIRST_UI_STANDARD_CHECK_ID_SET_MISMATCH"):
        _ = validate_degradation_first_ui_standard(payload)
