from __future__ import annotations

import pytest

from orket.runtime.sampling_discipline_guide import (
    sampling_discipline_guide_snapshot,
    validate_sampling_discipline_guide,
)


# Layer: unit
def test_sampling_discipline_guide_snapshot_contains_expected_event_classes() -> None:
    payload = sampling_discipline_guide_snapshot()
    assert payload["schema_version"] == "1.0"
    event_classes = {row["event_class"] for row in payload["rows"]}
    assert event_classes == {
        "fallback_event",
        "repair_event",
        "warning_event",
        "override_event",
    }


# Layer: contract
def test_validate_sampling_discipline_guide_accepts_current_snapshot() -> None:
    event_classes = validate_sampling_discipline_guide()
    assert "fallback_event" in event_classes


# Layer: contract
def test_validate_sampling_discipline_guide_rejects_event_class_set_mismatch() -> None:
    payload = sampling_discipline_guide_snapshot()
    payload["rows"] = [row for row in payload["rows"] if row["event_class"] != "override_event"]
    with pytest.raises(ValueError, match="E_SAMPLING_DISCIPLINE_GUIDE_EVENT_CLASS_SET_MISMATCH"):
        _ = validate_sampling_discipline_guide(payload)
