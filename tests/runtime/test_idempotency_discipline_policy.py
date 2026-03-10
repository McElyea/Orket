from __future__ import annotations

import pytest

from orket.runtime.idempotency_discipline_policy import (
    idempotency_discipline_policy_snapshot,
    validate_idempotency_discipline_policy,
)


# Layer: unit
def test_idempotency_discipline_policy_snapshot_contains_expected_surfaces() -> None:
    payload = idempotency_discipline_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    surfaces = {row["surface"] for row in payload["rows"]}
    assert surfaces == {
        "run_finalize",
        "artifact_write",
        "task_execution",
        "phase_transition",
        "tool_result_persist",
    }


# Layer: contract
def test_validate_idempotency_discipline_policy_accepts_current_snapshot() -> None:
    surfaces = validate_idempotency_discipline_policy()
    assert "run_finalize" in surfaces


# Layer: contract
def test_validate_idempotency_discipline_policy_rejects_surface_set_mismatch() -> None:
    payload = idempotency_discipline_policy_snapshot()
    payload["rows"] = [row for row in payload["rows"] if row["surface"] != "phase_transition"]
    with pytest.raises(ValueError, match="E_IDEMPOTENCY_DISCIPLINE_POLICY_SURFACE_SET_MISMATCH"):
        _ = validate_idempotency_discipline_policy(payload)
