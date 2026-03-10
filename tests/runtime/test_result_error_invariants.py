from __future__ import annotations

import pytest

from orket.runtime.result_error_invariants import (
    result_error_invariant_contract_snapshot,
    validate_result_error_invariant,
    validate_result_error_invariant_contract,
)


# Layer: unit
def test_validate_result_error_invariant_accepts_failed_with_failure_reason() -> None:
    assert (
        validate_result_error_invariant(
            status="failed",
            failure_class="ExecutionFailed",
            failure_reason="boom",
        )
        == "failed"
    )


# Layer: contract
def test_validate_result_error_invariant_rejects_done_with_failure() -> None:
    with pytest.raises(ValueError, match="E_RESULT_ERROR_INVARIANT:done_must_not_have_failure"):
        _ = validate_result_error_invariant(status="done", failure_reason="should not fail")


# Layer: contract
def test_validate_result_error_invariant_rejects_missing_status() -> None:
    with pytest.raises(ValueError, match="E_RESULT_ERROR_INVARIANT:status_required"):
        _ = validate_result_error_invariant(status="")


# Layer: contract
def test_result_error_invariant_contract_snapshot_contains_expected_statuses() -> None:
    payload = result_error_invariant_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["failure_forbidden_statuses"] == ["done", "incomplete", "running"]


# Layer: contract
def test_validate_result_error_invariant_contract_accepts_current_snapshot() -> None:
    statuses = validate_result_error_invariant_contract()
    assert statuses == ("done", "incomplete", "running")


# Layer: contract
def test_validate_result_error_invariant_contract_rejects_status_set_mismatch() -> None:
    payload = result_error_invariant_contract_snapshot()
    payload["failure_forbidden_statuses"] = ["done", "running"]
    with pytest.raises(ValueError, match="E_RESULT_ERROR_INVARIANT_CONTRACT_STATUS_SET_MISMATCH"):
        _ = validate_result_error_invariant_contract(payload)
