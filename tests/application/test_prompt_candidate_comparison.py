from __future__ import annotations

from scripts.prompt_lab.compare_candidates import (
    DEFAULT_THRESHOLDS_PATH,
    compare_candidate_against_stable,
)
from pathlib import Path


def test_compare_candidate_passes_without_regression() -> None:
    stable_eval = {
        "tool_parse_rate": 0.7,
        "required_action_completion_rate": 0.6,
        "status_progression_rate": 0.5,
        "guard_decision_reach_rate": 0.5,
    }
    candidate_eval = {
        "tool_parse_rate": 0.8,
        "required_action_completion_rate": 0.65,
        "status_progression_rate": 0.55,
        "guard_decision_reach_rate": 0.6,
    }
    stable_patterns = {
        "pattern_counters": {
            "turn_non_progress": 4,
            "tool_call_blocked": 1,
            "runtime_verifier_failures": 1,
            "done_chain_mismatch": 0,
            "guard_retry_scheduled": 1,
            "guard_terminal_failure": 0,
            "guard_terminal_reason_hallucination_persistent": 0,
            "turn_non_progress_hallucination_scope": 1,
            "turn_non_progress_security_scope": 1,
            "turn_non_progress_consistency_scope": 1,
        }
    }
    candidate_patterns = {
        "completion_by_model": {
            "model-a": {"runs": 2, "passed": 2, "failed": 0, "skipped": 0}
        },
        "pattern_counters": {
            "turn_non_progress": 3,
            "tool_call_blocked": 1,
            "runtime_verifier_failures": 0,
            "done_chain_mismatch": 0,
            "guard_retry_scheduled": 1,
            "guard_terminal_failure": 0,
            "guard_terminal_reason_hallucination_persistent": 0,
            "turn_non_progress_hallucination_scope": 1,
            "turn_non_progress_security_scope": 0,
            "turn_non_progress_consistency_scope": 0,
        }
    }
    report = compare_candidate_against_stable(
        stable_eval=stable_eval,
        candidate_eval=candidate_eval,
        stable_patterns=stable_patterns,
        candidate_patterns=candidate_patterns,
        thresholds={
            "candidate_guard_pass_rate_min": 0.95,
            "candidate_guard_terminal_failure_max": 0,
            "candidate_guard_terminal_reason_hallucination_persistent_max": 0,
            "candidate_done_chain_mismatch_max": 0,
        },
    )
    assert report["pass"] is True
    assert report["gates"]["turn_non_progress_max_increase"] is True
    assert report["blockers"] == []


def test_compare_candidate_fails_on_regression() -> None:
    stable_eval = {
        "tool_parse_rate": 0.8,
        "required_action_completion_rate": 0.7,
        "status_progression_rate": 0.7,
        "guard_decision_reach_rate": 0.6,
    }
    candidate_eval = {
        "tool_parse_rate": 0.7,
        "required_action_completion_rate": 0.6,
        "status_progression_rate": 0.6,
        "guard_decision_reach_rate": 0.5,
    }
    stable_patterns = {
        "pattern_counters": {
            "turn_non_progress": 1,
            "tool_call_blocked": 0,
            "runtime_verifier_failures": 0,
            "done_chain_mismatch": 0,
            "guard_retry_scheduled": 0,
            "guard_terminal_failure": 0,
            "guard_terminal_reason_hallucination_persistent": 0,
            "turn_non_progress_hallucination_scope": 0,
            "turn_non_progress_security_scope": 0,
            "turn_non_progress_consistency_scope": 0,
        }
    }
    candidate_patterns = {
        "completion_by_model": {
            "model-a": {"runs": 2, "passed": 0, "failed": 2, "skipped": 0}
        },
        "pattern_counters": {
            "turn_non_progress": 2,
            "tool_call_blocked": 1,
            "runtime_verifier_failures": 1,
            "done_chain_mismatch": 1,
            "guard_retry_scheduled": 1,
            "guard_terminal_failure": 1,
            "guard_terminal_reason_hallucination_persistent": 1,
            "turn_non_progress_hallucination_scope": 1,
            "turn_non_progress_security_scope": 1,
            "turn_non_progress_consistency_scope": 1,
        }
    }
    report = compare_candidate_against_stable(
        stable_eval=stable_eval,
        candidate_eval=candidate_eval,
        stable_patterns=stable_patterns,
        candidate_patterns=candidate_patterns,
        thresholds={
            "candidate_guard_pass_rate_min": 0.95,
            "candidate_guard_terminal_failure_max": 0,
            "candidate_guard_terminal_reason_hallucination_persistent_max": 0,
            "candidate_done_chain_mismatch_max": 0,
        },
    )
    assert report["pass"] is False
    assert report["gates"]["tool_parse_rate_min_delta"] is False
    assert report["gates"]["turn_non_progress_max_increase"] is False
    assert report["gates"]["guard_terminal_failure_max_increase"] is False
    assert report["criteria"]["candidate_guard_pass_rate_min"] is False
    assert report["criteria"]["candidate_guard_terminal_failure_max"] is False
    assert len(report["blockers"]) >= 1


def test_compare_candidate_custom_thresholds() -> None:
    report = compare_candidate_against_stable(
        stable_eval={
            "tool_parse_rate": 0.5,
            "required_action_completion_rate": 0.5,
            "status_progression_rate": 0.5,
            "guard_decision_reach_rate": 0.5,
        },
        candidate_eval={
            "tool_parse_rate": 0.52,
            "required_action_completion_rate": 0.52,
            "status_progression_rate": 0.52,
            "guard_decision_reach_rate": 0.52,
        },
        stable_patterns={"pattern_counters": {"turn_non_progress": 2, "tool_call_blocked": 0, "runtime_verifier_failures": 0, "done_chain_mismatch": 0}},
        candidate_patterns={"pattern_counters": {"turn_non_progress": 2, "tool_call_blocked": 0, "runtime_verifier_failures": 0, "done_chain_mismatch": 0}},
        thresholds={"tool_parse_rate_min_delta": 0.05},
    )
    assert report["pass"] is False
    assert report["gates"]["tool_parse_rate_min_delta"] is False


def test_compare_candidate_guard_domain_custom_thresholds() -> None:
    report = compare_candidate_against_stable(
        stable_eval={
            "tool_parse_rate": 0.5,
            "required_action_completion_rate": 0.5,
            "status_progression_rate": 0.5,
            "guard_decision_reach_rate": 0.5,
        },
        candidate_eval={
            "tool_parse_rate": 0.55,
            "required_action_completion_rate": 0.55,
            "status_progression_rate": 0.55,
            "guard_decision_reach_rate": 0.55,
        },
        stable_patterns={
            "pattern_counters": {
                "turn_non_progress": 2,
                "tool_call_blocked": 0,
                "runtime_verifier_failures": 0,
                "done_chain_mismatch": 0,
                "guard_retry_scheduled": 0,
                "guard_terminal_failure": 0,
                "guard_terminal_reason_hallucination_persistent": 0,
                "turn_non_progress_hallucination_scope": 0,
                "turn_non_progress_security_scope": 0,
                "turn_non_progress_consistency_scope": 0,
            }
        },
        candidate_patterns={
            "completion_by_model": {
                "model-a": {"runs": 2, "passed": 2, "failed": 0, "skipped": 0}
            },
            "pattern_counters": {
                "turn_non_progress": 2,
                "tool_call_blocked": 0,
                "runtime_verifier_failures": 0,
                "done_chain_mismatch": 0,
                "guard_retry_scheduled": 1,
                "guard_terminal_failure": 1,
                "guard_terminal_reason_hallucination_persistent": 1,
                "turn_non_progress_hallucination_scope": 1,
                "turn_non_progress_security_scope": 1,
                "turn_non_progress_consistency_scope": 1,
            }
        },
        thresholds={
            "guard_retry_scheduled_max_increase": 2,
            "guard_terminal_failure_max_increase": 1,
            "guard_terminal_reason_hallucination_persistent_max_increase": 1,
            "turn_non_progress_hallucination_scope_max_increase": 1,
            "turn_non_progress_security_scope_max_increase": 1,
            "turn_non_progress_consistency_scope_max_increase": 1,
            "candidate_guard_pass_rate_min": 0.95,
            "candidate_guard_terminal_failure_max": 1,
            "candidate_guard_terminal_reason_hallucination_persistent_max": 1,
            "candidate_done_chain_mismatch_max": 0,
        },
    )
    assert report["pass"] is True


def test_compare_candidate_exposes_machine_readable_blockers() -> None:
    report = compare_candidate_against_stable(
        stable_eval={
            "tool_parse_rate": 0.5,
            "required_action_completion_rate": 0.5,
            "status_progression_rate": 0.5,
            "guard_decision_reach_rate": 0.5,
        },
        candidate_eval={
            "tool_parse_rate": 0.4,
            "required_action_completion_rate": 0.4,
            "status_progression_rate": 0.4,
            "guard_decision_reach_rate": 0.4,
        },
        stable_patterns={"pattern_counters": {"guard_terminal_failure": 0}},
        candidate_patterns={
            "completion_by_model": {"model-a": {"runs": 1, "passed": 0, "failed": 1, "skipped": 0}},
            "pattern_counters": {"guard_terminal_failure": 1, "done_chain_mismatch": 1},
        },
        thresholds={
            "tool_parse_rate_min_delta": 0.0,
            "candidate_guard_pass_rate_min": 0.95,
            "candidate_guard_terminal_failure_max": 0,
            "candidate_done_chain_mismatch_max": 0,
        },
    )
    assert report["pass"] is False
    assert any(item["type"] == "gate" for item in report["blockers"])
    assert any(item["type"] == "criteria" for item in report["blockers"])


def test_compare_candidates_default_thresholds_file_exists() -> None:
    assert Path(DEFAULT_THRESHOLDS_PATH).exists()
