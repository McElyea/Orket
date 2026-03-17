from __future__ import annotations

from scripts.governance.check_source_attribution_policy import evaluate_source_attribution_policy


# Layer: contract
def test_check_source_attribution_policy_passes_for_current_snapshot() -> None:
    payload = evaluate_source_attribution_policy()
    assert payload["ok"] is True
    assert payload["mode_count"] == 2
