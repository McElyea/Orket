from __future__ import annotations

import pytest

from orket.runtime.execution_readiness_rubric import (
    execution_readiness_rubric_snapshot,
    validate_execution_readiness_rubric,
)


# Layer: unit
def test_execution_readiness_rubric_snapshot_contains_expected_criteria() -> None:
    payload = execution_readiness_rubric_snapshot()
    assert payload["schema_version"] == "1.0"
    criteria = {row["criterion"] for row in payload["criteria"]}
    assert criteria == {
        "contract_drift_clean",
        "acceptance_gate_green",
        "runtime_boundary_audit_passed",
        "docs_hygiene_passed",
    }


# Layer: contract
def test_validate_execution_readiness_rubric_accepts_current_snapshot() -> None:
    criteria = validate_execution_readiness_rubric()
    assert "acceptance_gate_green" in criteria


# Layer: contract
def test_validate_execution_readiness_rubric_rejects_criteria_set_mismatch() -> None:
    payload = execution_readiness_rubric_snapshot()
    payload["criteria"] = [row for row in payload["criteria"] if row["criterion"] != "docs_hygiene_passed"]
    with pytest.raises(ValueError, match="E_EXECUTION_READINESS_RUBRIC_CRITERIA_SET_MISMATCH"):
        _ = validate_execution_readiness_rubric(payload)
