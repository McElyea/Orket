from __future__ import annotations

import pytest

from orket.runtime.human_correction_capture_policy import (
    human_correction_capture_policy_snapshot,
    validate_human_correction_capture_policy,
)


# Layer: unit
def test_human_correction_capture_policy_snapshot_contains_expected_target_surfaces() -> None:
    payload = human_correction_capture_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    target_surfaces = set(payload["target_surfaces"])
    assert "route_decision" in target_surfaces
    assert "final_response" in target_surfaces


# Layer: contract
def test_validate_human_correction_capture_policy_accepts_current_snapshot() -> None:
    target_surfaces = validate_human_correction_capture_policy()
    assert "route_decision" in target_surfaces


# Layer: contract
def test_validate_human_correction_capture_policy_rejects_target_surface_mismatch() -> None:
    payload = human_correction_capture_policy_snapshot()
    payload["target_surfaces"] = [surface for surface in payload["target_surfaces"] if surface != "route_decision"]
    with pytest.raises(ValueError, match="E_HUMAN_CORRECTION_CAPTURE_TARGET_SURFACES_MISMATCH"):
        _ = validate_human_correction_capture_policy(payload)
