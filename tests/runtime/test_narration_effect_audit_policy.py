from __future__ import annotations

import pytest

from orket.runtime.narration_effect_audit_policy import (
    narration_effect_audit_policy_snapshot,
    validate_narration_effect_audit_policy,
)


# Layer: unit
def test_narration_effect_audit_policy_snapshot_contains_expected_tools() -> None:
    payload = narration_effect_audit_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    assert set(payload["audit_statuses"]) == {"missing", "verified"}
    tools = {row["tool"] for row in payload["rows"]}
    assert tools == {"update_issue_status", "write_file"}


# Layer: contract
def test_validate_narration_effect_audit_policy_accepts_current_snapshot() -> None:
    tools = validate_narration_effect_audit_policy()
    assert "write_file" in tools


# Layer: contract
def test_validate_narration_effect_audit_policy_rejects_tool_set_mismatch() -> None:
    payload = narration_effect_audit_policy_snapshot()
    payload["rows"] = [row for row in payload["rows"] if row["tool"] != "write_file"]
    with pytest.raises(ValueError, match="E_NARRATION_EFFECT_AUDIT_POLICY_TOOL_SET_MISMATCH"):
        _ = validate_narration_effect_audit_policy(payload)
