from __future__ import annotations

import pytest

from orket.runtime.result_error_invariants import validate_result_error_invariant


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
