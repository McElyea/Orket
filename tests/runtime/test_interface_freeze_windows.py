from __future__ import annotations

import pytest

from orket.runtime.interface_freeze_windows import (
    interface_freeze_windows_snapshot,
    validate_interface_freeze_windows,
)


# Layer: unit
def test_interface_freeze_windows_snapshot_contains_expected_window_ids() -> None:
    payload = interface_freeze_windows_snapshot()
    assert payload["schema_version"] == "1.0"
    window_ids = {row["window_id"] for row in payload["windows"]}
    assert window_ids == {
        "pre_promotion_contract_freeze",
        "promotion_candidate_interface_freeze",
        "post_promotion_observation_freeze",
    }


# Layer: contract
def test_validate_interface_freeze_windows_accepts_current_snapshot() -> None:
    window_ids = validate_interface_freeze_windows()
    assert "promotion_candidate_interface_freeze" in window_ids


# Layer: contract
def test_validate_interface_freeze_windows_rejects_window_set_mismatch() -> None:
    payload = interface_freeze_windows_snapshot()
    payload["windows"] = [
        row for row in payload["windows"] if row["window_id"] != "post_promotion_observation_freeze"
    ]
    with pytest.raises(ValueError, match="E_INTERFACE_FREEZE_WINDOWS_ID_SET_MISMATCH"):
        _ = validate_interface_freeze_windows(payload)
