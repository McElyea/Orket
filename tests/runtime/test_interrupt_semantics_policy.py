from __future__ import annotations

import pytest

from orket.runtime.interrupt_semantics_policy import (
    interrupt_semantics_policy_snapshot,
    validate_interrupt_semantics_policy,
)


# Layer: unit
def test_interrupt_semantics_policy_snapshot_contains_expected_surfaces() -> None:
    payload = interrupt_semantics_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    surfaces = {row["surface"] for row in payload["rows"]}
    assert surfaces == {
        "run_execution",
        "tool_invocation",
        "streaming_output",
        "voice_playback",
        "ui_render",
    }


# Layer: contract
def test_validate_interrupt_semantics_policy_accepts_current_snapshot() -> None:
    surfaces = validate_interrupt_semantics_policy()
    assert "run_execution" in surfaces


# Layer: contract
def test_validate_interrupt_semantics_policy_rejects_surface_set_mismatch() -> None:
    payload = interrupt_semantics_policy_snapshot()
    payload["rows"] = [row for row in payload["rows"] if row["surface"] != "ui_render"]
    with pytest.raises(ValueError, match="E_INTERRUPT_SEMANTICS_POLICY_SURFACE_SET_MISMATCH"):
        _ = validate_interrupt_semantics_policy(payload)
