from __future__ import annotations

import pytest

from orket.runtime.spec_debt_queue import spec_debt_queue_snapshot, validate_spec_debt_queue


# Layer: unit
def test_spec_debt_queue_snapshot_contains_expected_debt_types() -> None:
    payload = spec_debt_queue_snapshot()
    assert payload["schema_version"] == "1.0"
    debt_types = {row["debt_type"] for row in payload["entries"]}
    assert debt_types == {"doc_runtime_drift", "schema_gap", "test_taxonomy_gap"}


# Layer: contract
def test_validate_spec_debt_queue_accepts_current_snapshot() -> None:
    debt_ids = validate_spec_debt_queue()
    assert "SDQ-001" in debt_ids


# Layer: contract
def test_validate_spec_debt_queue_rejects_debt_type_set_mismatch() -> None:
    payload = spec_debt_queue_snapshot()
    payload["entries"] = [row for row in payload["entries"] if row["debt_type"] != "test_taxonomy_gap"]
    with pytest.raises(ValueError, match="E_SPEC_DEBT_QUEUE_DEBT_TYPE_SET_MISMATCH"):
        _ = validate_spec_debt_queue(payload)
