from __future__ import annotations

import pytest

from orket.runtime.ui_lane_security_boundary_test_contract import (
    ui_lane_security_boundary_test_contract_snapshot,
    validate_ui_lane_security_boundary_test_contract,
)


# Layer: unit
def test_ui_lane_security_boundary_test_contract_snapshot_contains_expected_check_ids() -> None:
    payload = ui_lane_security_boundary_test_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "explorer_path_traversal_blocked",
        "session_workspace_escape_blocked",
        "companion_error_mapping_is_structured",
        "ui_state_registry_blocked_boundary_enforced",
    }


# Layer: contract
def test_validate_ui_lane_security_boundary_test_contract_accepts_current_snapshot() -> None:
    check_ids = validate_ui_lane_security_boundary_test_contract()
    assert "ui_state_registry_blocked_boundary_enforced" in check_ids


# Layer: contract
def test_validate_ui_lane_security_boundary_test_contract_rejects_check_set_mismatch() -> None:
    payload = ui_lane_security_boundary_test_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "explorer_path_traversal_blocked"]
    with pytest.raises(ValueError, match="E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_ui_lane_security_boundary_test_contract(payload)
