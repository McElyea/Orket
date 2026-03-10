from __future__ import annotations

import pytest

from orket.runtime.release_confidence_scorecard import (
    release_confidence_scorecard_snapshot,
    validate_release_confidence_scorecard,
)


# Layer: unit
def test_release_confidence_scorecard_snapshot_contains_expected_dimensions() -> None:
    payload = release_confidence_scorecard_snapshot()
    assert payload["schema_version"] == "1.0"
    dimensions = {row["name"] for row in payload["dimensions"]}
    assert dimensions == {
        "correctness",
        "degradation",
        "repair_visibility",
        "conformance",
        "trust_signal",
    }


# Layer: contract
def test_validate_release_confidence_scorecard_accepts_current_snapshot() -> None:
    dimensions = validate_release_confidence_scorecard()
    assert "correctness" in dimensions


# Layer: contract
def test_validate_release_confidence_scorecard_rejects_dimension_set_mismatch() -> None:
    payload = release_confidence_scorecard_snapshot()
    payload["dimensions"] = [row for row in payload["dimensions"] if row["name"] != "trust_signal"]
    with pytest.raises(ValueError, match="E_RELEASE_CONFIDENCE_SCORECARD_DIMENSION_SET_MISMATCH"):
        _ = validate_release_confidence_scorecard(payload)
