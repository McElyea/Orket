# LIFECYCLE: live
from __future__ import annotations

from scripts.governance.check_narration_effect_audit_policy import evaluate_narration_effect_audit_policy


# Layer: contract
def test_check_narration_effect_audit_policy_passes_for_current_snapshot() -> None:
    payload = evaluate_narration_effect_audit_policy()
    assert payload["ok"] is True
    assert payload["tool_count"] == 2
