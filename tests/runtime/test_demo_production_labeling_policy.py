from __future__ import annotations

import pytest

from orket.runtime.demo_production_labeling_policy import (
    demo_production_labeling_policy_snapshot,
    validate_demo_production_labeling_policy,
)


# Layer: unit
def test_demo_production_labeling_policy_snapshot_contains_expected_labels() -> None:
    payload = demo_production_labeling_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    labels = set(payload["labels"])
    assert "production_verified" in labels
    assert "demo_simulated" in labels


# Layer: contract
def test_validate_demo_production_labeling_policy_accepts_current_snapshot() -> None:
    labels = validate_demo_production_labeling_policy()
    assert "production_verified" in labels


# Layer: contract
def test_validate_demo_production_labeling_policy_rejects_label_mismatch() -> None:
    payload = demo_production_labeling_policy_snapshot()
    payload["labels"] = [label for label in payload["labels"] if label != "demo_simulated"]
    with pytest.raises(ValueError, match="E_DEMO_PRODUCTION_LABELING_LABELS_MISMATCH"):
        _ = validate_demo_production_labeling_policy(payload)
