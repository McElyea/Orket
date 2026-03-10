from __future__ import annotations

import pytest

from orket.runtime.cold_start_truth_test_contract import (
    cold_start_truth_test_contract_snapshot,
    validate_cold_start_truth_test_contract,
)


# Layer: unit
def test_cold_start_truth_test_contract_snapshot_contains_expected_check_ids() -> None:
    payload = cold_start_truth_test_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "stub_cold_start_true_loading_payload",
        "stub_cold_start_false_loading_payload",
        "stub_loading_precedes_ready_event",
    }


# Layer: contract
def test_validate_cold_start_truth_test_contract_accepts_current_snapshot() -> None:
    check_ids = validate_cold_start_truth_test_contract()
    assert "stub_loading_precedes_ready_event" in check_ids


# Layer: contract
def test_validate_cold_start_truth_test_contract_rejects_check_set_mismatch() -> None:
    payload = cold_start_truth_test_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "stub_loading_precedes_ready_event"]
    with pytest.raises(ValueError, match="E_COLD_START_TRUTH_TEST_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_cold_start_truth_test_contract(payload)
