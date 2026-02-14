from __future__ import annotations

import json
from pathlib import Path


def test_prompt_promotion_thresholds_file_has_required_guard_keys() -> None:
    path = Path("benchmarks/results/prompt_promotion_thresholds.json")
    assert path.exists(), "Missing canonical prompt promotion thresholds file."
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)

    required_keys = {
        "tool_parse_rate_min_delta",
        "required_action_completion_rate_min_delta",
        "status_progression_rate_min_delta",
        "guard_decision_reach_rate_min_delta",
        "turn_non_progress_max_increase",
        "tool_call_blocked_max_increase",
        "runtime_verifier_failures_max_increase",
        "done_chain_mismatch_max_increase",
        "guard_retry_scheduled_max_increase",
        "guard_terminal_failure_max_increase",
        "guard_terminal_reason_hallucination_persistent_max_increase",
        "turn_non_progress_hallucination_scope_max_increase",
        "turn_non_progress_security_scope_max_increase",
        "turn_non_progress_consistency_scope_max_increase",
    }
    missing = sorted(required_keys.difference(payload.keys()))
    assert not missing, "Missing required promotion threshold keys: " + ", ".join(missing)

    non_numeric = sorted(
        key for key in required_keys if not isinstance(payload.get(key), (int, float))
    )
    assert not non_numeric, "Threshold values must be numeric: " + ", ".join(non_numeric)
