from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _average_compliance_score(report: Dict[str, Any]) -> float:
    model_compliance = report.get("model_compliance", {})
    if not isinstance(model_compliance, dict) or not model_compliance:
        return 0.0
    values = []
    for value in model_compliance.values():
        if not isinstance(value, dict):
            continue
        score = value.get("compliance_score")
        try:
            values.append(float(score))
        except (TypeError, ValueError):
            continue
    if not values:
        return 0.0
    return sum(values) / len(values)


def _canonical_success_rate(report: Dict[str, Any]) -> float:
    completion = report.get("completion_by_model", {})
    if not isinstance(completion, dict) or not completion:
        return 0.0
    runs = 0
    passed = 0
    for value in completion.values():
        if not isinstance(value, dict):
            continue
        runs += int(value.get("runs", 0) or 0)
        passed += int(value.get("passed", 0) or 0)
    if runs <= 0:
        return 0.0
    return float(passed) / float(runs)


def evaluate_policy_release_gate(
    *,
    previous_report: Dict[str, Any],
    current_report: Dict[str, Any],
    min_compliance_delta: float = 0.0,
    min_success_rate_delta: float = 0.0,
) -> Dict[str, Any]:
    previous_score = _average_compliance_score(previous_report)
    current_score = _average_compliance_score(current_report)
    previous_success = _canonical_success_rate(previous_report)
    current_success = _canonical_success_rate(current_report)

    compliance_delta = current_score - previous_score
    success_delta = current_success - previous_success
    compliance_ok = compliance_delta > float(min_compliance_delta)
    success_ok = success_delta > float(min_success_rate_delta)

    ok = compliance_ok or success_ok
    return {
        "ok": ok,
        "previous_avg_compliance_score": previous_score,
        "current_avg_compliance_score": current_score,
        "compliance_delta": compliance_delta,
        "previous_success_rate": previous_success,
        "current_success_rate": current_success,
        "success_rate_delta": success_delta,
        "thresholds": {
            "min_compliance_delta": float(min_compliance_delta),
            "min_success_rate_delta": float(min_success_rate_delta),
        },
        "checks": {
            "compliance_delta_ok": compliance_ok,
            "success_rate_delta_ok": success_ok,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Release gate: policy churn must show measurable reliability improvement."
    )
    parser.add_argument("--previous-report", required=True, help="Path to previous pattern report JSON.")
    parser.add_argument("--current-report", required=True, help="Path to current pattern report JSON.")
    parser.add_argument("--policy-churn", action="store_true", help="Enable strict enforcement when policy changed.")
    parser.add_argument("--min-compliance-delta", type=float, default=0.0)
    parser.add_argument("--min-success-rate-delta", type=float, default=0.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    previous = _load_json(Path(args.previous_report))
    current = _load_json(Path(args.current_report))
    result = evaluate_policy_release_gate(
        previous_report=previous,
        current_report=current,
        min_compliance_delta=float(args.min_compliance_delta),
        min_success_rate_delta=float(args.min_success_rate_delta),
    )
    print(json.dumps(result, indent=2))
    if args.policy_churn and not result.get("ok", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
