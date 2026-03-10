from __future__ import annotations

import pytest

from orket.runtime.persistence_corruption_test_contract import (
    persistence_corruption_test_contract_snapshot,
    validate_persistence_corruption_test_contract,
)


# Layer: unit
def test_persistence_corruption_test_contract_snapshot_contains_expected_check_ids() -> None:
    payload = persistence_corruption_test_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "checksum_corruption_rejected",
        "non_monotonic_sequence_rejected",
        "partial_tail_replayed_safely",
    }


# Layer: contract
def test_validate_persistence_corruption_test_contract_accepts_current_snapshot() -> None:
    check_ids = validate_persistence_corruption_test_contract()
    assert "checksum_corruption_rejected" in check_ids
    assert "partial_tail_replayed_safely" in check_ids


# Layer: contract
def test_validate_persistence_corruption_test_contract_rejects_check_set_mismatch() -> None:
    payload = persistence_corruption_test_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "partial_tail_replayed_safely"]
    with pytest.raises(ValueError, match="E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_persistence_corruption_test_contract(payload)


# Layer: contract
def test_validate_persistence_corruption_test_contract_rejects_safe_recovery_with_error_code() -> None:
    payload = persistence_corruption_test_contract_snapshot()
    payload["checks"][-1]["expected_error_code"] = "E_LEDGER_CORRUPT"
    with pytest.raises(ValueError, match="E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_ERROR_CODE_FORBIDDEN"):
        _ = validate_persistence_corruption_test_contract(payload)
