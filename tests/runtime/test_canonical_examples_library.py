from __future__ import annotations

import pytest

from orket.runtime.canonical_examples_library import (
    canonical_examples_library_snapshot,
    validate_canonical_examples_library,
)


# Layer: unit
def test_canonical_examples_library_snapshot_contains_expected_ids() -> None:
    payload = canonical_examples_library_snapshot()
    assert payload["schema_version"] == "1.0"
    example_ids = {row["example_id"] for row in payload["examples"]}
    assert example_ids == {
        "EX-ROUTE-DECISION-BASELINE",
        "EX-REPAIR-LEDGER-BASELINE",
        "EX-DEGRADATION-LABELING-BASELINE",
        "EX-OPERATOR-OVERRIDE-BASELINE",
    }


# Layer: contract
def test_validate_canonical_examples_library_accepts_current_snapshot() -> None:
    example_ids = validate_canonical_examples_library()
    assert "EX-ROUTE-DECISION-BASELINE" in example_ids


# Layer: contract
def test_validate_canonical_examples_library_rejects_id_set_mismatch() -> None:
    payload = canonical_examples_library_snapshot()
    payload["examples"] = [row for row in payload["examples"] if row["example_id"] != "EX-OPERATOR-OVERRIDE-BASELINE"]
    with pytest.raises(ValueError, match="E_CANONICAL_EXAMPLES_LIBRARY_ID_SET_MISMATCH"):
        _ = validate_canonical_examples_library(payload)
