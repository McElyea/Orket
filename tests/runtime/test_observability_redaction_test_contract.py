from __future__ import annotations

import pytest

from orket.runtime.observability_redaction_test_contract import (
    observability_redaction_test_contract_snapshot,
    validate_observability_redaction_test_contract,
)


# Layer: unit
def test_observability_redaction_test_contract_snapshot_contains_expected_check_ids() -> None:
    payload = observability_redaction_test_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    check_ids = {row["check_id"] for row in payload["checks"]}
    assert check_ids == {
        "env_secret_values_masked",
        "env_non_secret_values_preserved",
        "env_long_values_truncated",
        "workload_snapshot_redaction_shape",
    }


# Layer: contract
def test_validate_observability_redaction_test_contract_accepts_current_snapshot() -> None:
    check_ids = validate_observability_redaction_test_contract()
    assert "env_secret_values_masked" in check_ids


# Layer: contract
def test_validate_observability_redaction_test_contract_rejects_check_set_mismatch() -> None:
    payload = observability_redaction_test_contract_snapshot()
    payload["checks"] = [row for row in payload["checks"] if row["check_id"] != "env_long_values_truncated"]
    with pytest.raises(ValueError, match="E_OBSERVABILITY_REDACTION_TEST_CONTRACT_CHECK_ID_SET_MISMATCH"):
        _ = validate_observability_redaction_test_contract(payload)
