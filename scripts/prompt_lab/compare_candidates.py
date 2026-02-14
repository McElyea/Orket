from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_THRESHOLDS_PATH = Path("benchmarks/results/prompt_promotion_thresholds.json")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(payload: Dict[str, Any], key: str) -> float:
    value = payload.get(key, 0.0)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _metrics_delta(stable: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, float]:
    keys = [
        "tool_parse_rate",
        "required_action_completion_rate",
        "status_progression_rate",
        "guard_decision_reach_rate",
    ]
    return {key: _num(candidate, key) - _num(stable, key) for key in keys}


def _pattern_delta(stable: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, int]:
    stable_patterns = (stable.get("pattern_counters") or {}) if isinstance(stable, dict) else {}
    candidate_patterns = (candidate.get("pattern_counters") or {}) if isinstance(candidate, dict) else {}
    keys = [
        "turn_non_progress",
        "tool_call_blocked",
        "runtime_verifier_failures",
        "done_chain_mismatch",
        "guard_retry_scheduled",
        "guard_terminal_failure",
        "guard_terminal_reason_hallucination_persistent",
        "turn_non_progress_hallucination_scope",
        "turn_non_progress_security_scope",
        "turn_non_progress_consistency_scope",
    ]
    delta: Dict[str, int] = {}
    for key in keys:
        s = stable_patterns.get(key, 0)
        c = candidate_patterns.get(key, 0)
        s_i = int(s) if isinstance(s, (int, float)) else 0
        c_i = int(c) if isinstance(c, (int, float)) else 0
        delta[key] = c_i - s_i
    return delta


def _pattern_value(payload: Dict[str, Any], key: str) -> int:
    patterns = (payload.get("pattern_counters") or {}) if isinstance(payload, dict) else {}
    value = patterns.get(key, 0)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _candidate_guard_pass_rate(payload: Dict[str, Any]) -> Optional[float]:
    completion = payload.get("completion_by_model")
    if not isinstance(completion, dict) or not completion:
        return None
    passed = 0
    failed = 0
    for stats in completion.values():
        if not isinstance(stats, dict):
            continue
        passed += int(stats.get("passed", 0) or 0)
        failed += int(stats.get("failed", 0) or 0)
    denom = passed + failed
    if denom <= 0:
        return None
    return float(passed) / float(denom)


def _threshold_value(thresholds: Dict[str, Any], key: str, default: float) -> float:
    value = thresholds.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    return float(default)


def evaluate_promotion_gates(
    *,
    eval_delta: Dict[str, float],
    pattern_delta: Dict[str, int],
    candidate_patterns: Dict[str, Any],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    gates = {
        "tool_parse_rate_min_delta": eval_delta.get("tool_parse_rate", 0.0)
        >= _threshold_value(thresholds, "tool_parse_rate_min_delta", 0.0),
        "required_action_completion_rate_min_delta": eval_delta.get("required_action_completion_rate", 0.0)
        >= _threshold_value(thresholds, "required_action_completion_rate_min_delta", 0.0),
        "status_progression_rate_min_delta": eval_delta.get("status_progression_rate", 0.0)
        >= _threshold_value(thresholds, "status_progression_rate_min_delta", 0.0),
        "guard_decision_reach_rate_min_delta": eval_delta.get("guard_decision_reach_rate", 0.0)
        >= _threshold_value(thresholds, "guard_decision_reach_rate_min_delta", 0.0),
        "turn_non_progress_max_increase": pattern_delta.get("turn_non_progress", 0)
        <= int(_threshold_value(thresholds, "turn_non_progress_max_increase", 0)),
        "tool_call_blocked_max_increase": pattern_delta.get("tool_call_blocked", 0)
        <= int(_threshold_value(thresholds, "tool_call_blocked_max_increase", 0)),
        "runtime_verifier_failures_max_increase": pattern_delta.get("runtime_verifier_failures", 0)
        <= int(_threshold_value(thresholds, "runtime_verifier_failures_max_increase", 0)),
        "done_chain_mismatch_max_increase": pattern_delta.get("done_chain_mismatch", 0)
        <= int(_threshold_value(thresholds, "done_chain_mismatch_max_increase", 0)),
        "guard_retry_scheduled_max_increase": pattern_delta.get("guard_retry_scheduled", 0)
        <= int(_threshold_value(thresholds, "guard_retry_scheduled_max_increase", 0)),
        "guard_terminal_failure_max_increase": pattern_delta.get("guard_terminal_failure", 0)
        <= int(_threshold_value(thresholds, "guard_terminal_failure_max_increase", 0)),
        "guard_terminal_reason_hallucination_persistent_max_increase": pattern_delta.get(
            "guard_terminal_reason_hallucination_persistent", 0
        )
        <= int(
            _threshold_value(
                thresholds, "guard_terminal_reason_hallucination_persistent_max_increase", 0
            )
        ),
        "turn_non_progress_hallucination_scope_max_increase": pattern_delta.get(
            "turn_non_progress_hallucination_scope", 0
        )
        <= int(_threshold_value(thresholds, "turn_non_progress_hallucination_scope_max_increase", 0)),
        "turn_non_progress_security_scope_max_increase": pattern_delta.get(
            "turn_non_progress_security_scope", 0
        )
        <= int(_threshold_value(thresholds, "turn_non_progress_security_scope_max_increase", 0)),
        "turn_non_progress_consistency_scope_max_increase": pattern_delta.get(
            "turn_non_progress_consistency_scope", 0
        )
        <= int(_threshold_value(thresholds, "turn_non_progress_consistency_scope_max_increase", 0)),
    }
    candidate_guard_pass_rate = _candidate_guard_pass_rate(candidate_patterns)
    criteria: Dict[str, Optional[bool]] = {}
    criteria_values: Dict[str, Any] = {}

    guard_pass_rate_min = thresholds.get("candidate_guard_pass_rate_min")
    if isinstance(guard_pass_rate_min, (int, float)):
        if candidate_guard_pass_rate is None:
            criteria["candidate_guard_pass_rate_min"] = False
            criteria_values["candidate_guard_pass_rate"] = None
        else:
            criteria["candidate_guard_pass_rate_min"] = candidate_guard_pass_rate >= float(guard_pass_rate_min)
            criteria_values["candidate_guard_pass_rate"] = candidate_guard_pass_rate

    candidate_guard_terminal_failure = _pattern_value(candidate_patterns, "guard_terminal_failure")
    candidate_terminal_failure_max = thresholds.get("candidate_guard_terminal_failure_max")
    if isinstance(candidate_terminal_failure_max, (int, float)):
        criteria["candidate_guard_terminal_failure_max"] = (
            candidate_guard_terminal_failure <= int(candidate_terminal_failure_max)
        )
        criteria_values["candidate_guard_terminal_failure"] = candidate_guard_terminal_failure

    candidate_hallucination_persistent = _pattern_value(
        candidate_patterns, "guard_terminal_reason_hallucination_persistent"
    )
    candidate_hallucination_persistent_max = thresholds.get(
        "candidate_guard_terminal_reason_hallucination_persistent_max"
    )
    if isinstance(candidate_hallucination_persistent_max, (int, float)):
        criteria["candidate_guard_terminal_reason_hallucination_persistent_max"] = (
            candidate_hallucination_persistent <= int(candidate_hallucination_persistent_max)
        )
        criteria_values[
            "candidate_guard_terminal_reason_hallucination_persistent"
        ] = candidate_hallucination_persistent

    candidate_done_chain_mismatch = _pattern_value(candidate_patterns, "done_chain_mismatch")
    candidate_done_chain_mismatch_max = thresholds.get("candidate_done_chain_mismatch_max")
    if isinstance(candidate_done_chain_mismatch_max, (int, float)):
        criteria["candidate_done_chain_mismatch_max"] = (
            candidate_done_chain_mismatch <= int(candidate_done_chain_mismatch_max)
        )
        criteria_values["candidate_done_chain_mismatch"] = candidate_done_chain_mismatch

    blockers: List[Dict[str, Any]] = []
    for gate_key, passed in gates.items():
        if not passed:
            blockers.append(
                {
                    "code": f"GATE_{gate_key.upper()}",
                    "type": "gate",
                    "message": f"Promotion gate failed: {gate_key}",
                }
            )
    for criteria_key, passed in criteria.items():
        if passed is False:
            blockers.append(
                {
                    "code": f"CRITERIA_{criteria_key.upper()}",
                    "type": "criteria",
                    "message": f"Promotion criteria failed: {criteria_key}",
                }
            )

    return {
        "pass": all(gates.values()) and all(value is True for value in criteria.values()),
        "gates": gates,
        "criteria": criteria,
        "criteria_values": criteria_values,
        "blockers": blockers,
    }


def compare_candidate_against_stable(
    *,
    stable_eval: Dict[str, Any],
    candidate_eval: Dict[str, Any],
    stable_patterns: Dict[str, Any],
    candidate_patterns: Dict[str, Any],
    thresholds: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    eval_delta = _metrics_delta(stable_eval, candidate_eval)
    pattern_delta = _pattern_delta(stable_patterns, candidate_patterns)
    thresholds = dict(thresholds or {})
    gate_eval = evaluate_promotion_gates(
        eval_delta=eval_delta,
        pattern_delta=pattern_delta,
        candidate_patterns=candidate_patterns,
        thresholds=thresholds,
    )
    return {
        "pass": gate_eval["pass"],
        "eval_delta": eval_delta,
        "pattern_delta": pattern_delta,
        "thresholds": thresholds,
        "gates": gate_eval["gates"],
        "criteria": gate_eval["criteria"],
        "criteria_values": gate_eval["criteria_values"],
        "blockers": gate_eval["blockers"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare candidate prompt run metrics against stable baseline."
    )
    parser.add_argument("--stable-eval", required=True, help="Path to stable prompt_eval_metrics.json")
    parser.add_argument("--candidate-eval", required=True, help="Path to candidate prompt_eval_metrics.json")
    parser.add_argument("--stable-patterns", required=True, help="Path to stable live acceptance report JSON")
    parser.add_argument("--candidate-patterns", required=True, help="Path to candidate live acceptance report JSON")
    parser.add_argument(
        "--thresholds",
        default=str(DEFAULT_THRESHOLDS_PATH),
        help="Optional JSON file with promotion gate thresholds.",
    )
    parser.add_argument("--out", default="", help="Optional output report path")
    args = parser.parse_args(argv)

    thresholds = {}
    threshold_path = str(args.thresholds or "").strip()
    if threshold_path:
        candidate = Path(threshold_path)
        if candidate.exists():
            thresholds = _load_json(candidate)

    report = compare_candidate_against_stable(
        stable_eval=_load_json(Path(args.stable_eval)),
        candidate_eval=_load_json(Path(args.candidate_eval)),
        stable_patterns=_load_json(Path(args.stable_patterns)),
        candidate_patterns=_load_json(Path(args.candidate_patterns)),
        thresholds=thresholds,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
