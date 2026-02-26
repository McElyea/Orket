from __future__ import annotations

from statistics import mean, pvariance
from typing import Any, Dict, Iterable


DEFAULT_WEIGHTS = {
    "forbidden_hit": 30,
    "anti_hallucination_hit": 30,
    "reopened_issue": 20,
    "missing_section": 10,
    "unresolved_last": 5,
    "converged_bonus": 10,
    "oscillation_hit": 10,
}


def score_run(result: Dict[str, Any], scoring: Dict[str, Any]) -> Dict[str, Any]:
    weights = dict(DEFAULT_WEIGHTS)
    if isinstance(scoring.get("weights"), dict):
        for key, value in scoring["weights"].items():
            try:
                weights[str(key)] = float(value)
            except (TypeError, ValueError):
                continue

    forbidden_hits = int(result.get("forbidden_hits", 0))
    anti_hallucination_hits = int(result.get("anti_hallucination_hits", 0))
    reopened_issues = int(result.get("reopened_issues", 0))
    missing_sections = int(result.get("missing_required_sections", 0))
    unresolved_counts = [int(v) for v in (result.get("unresolved_counts") or [])]
    unresolved_last = unresolved_counts[-1] if unresolved_counts else 0
    rounds_to_zero = int(result.get("rounds_to_zero", 0))
    oscillation_hits = int(result.get("oscillation_hits", 0))

    hard_fail = forbidden_hits > 0 or anti_hallucination_hits > 0 or reopened_issues > 0

    penalties = {
        "forbidden": forbidden_hits * weights["forbidden_hit"],
        "anti_hallucination": anti_hallucination_hits * weights["anti_hallucination_hit"],
        "reopened": reopened_issues * weights["reopened_issue"],
        "missing_sections": missing_sections * weights["missing_section"],
        "unresolved_last": unresolved_last * weights["unresolved_last"],
        "oscillation": oscillation_hits * weights["oscillation_hit"],
    }
    bonuses = {
        "converged": weights["converged_bonus"] if rounds_to_zero > 0 else 0.0,
    }
    total = float(sum(penalties.values()) - sum(bonuses.values()))
    if hard_fail:
        total += 1000.0
    return {
        "hard_fail": hard_fail,
        "penalties": penalties,
        "bonuses": bonuses,
        "score_total": total,
    }


def aggregate_pairing(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    seq = list(rows)
    if not seq:
        return {"run_count": 0, "mean_score": None, "variance_score": None, "hard_fail_rate": None}
    scores = [float(item.get("score_total", 0.0)) for item in seq]
    hard_fails = [1 if bool(item.get("hard_fail")) else 0 for item in seq]
    return {
        "run_count": len(seq),
        "mean_score": mean(scores),
        "variance_score": pvariance(scores) if len(scores) > 1 else 0.0,
        "hard_fail_rate": sum(hard_fails) / len(hard_fails),
    }
