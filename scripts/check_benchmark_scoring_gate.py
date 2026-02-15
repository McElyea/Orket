from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate benchmark scoring metadata and threshold gates.")
    parser.add_argument("--scored-report", default="benchmarks/results/benchmark_scored_report.json")
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--out", default="benchmarks/results/benchmark_scoring_gate.json")
    parser.add_argument(
        "--require-thresholds",
        action="store_true",
        help="Exit non-zero if threshold checks fail.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_gate(scored: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    per_task = scored.get("per_task_scores")
    if not isinstance(per_task, dict) or not per_task:
        failures.append("missing per_task_scores")
        per_task = {}

    tier_scores = scored.get("aggregate_tier_scores")
    if not isinstance(tier_scores, dict) or not tier_scores:
        failures.append("missing aggregate_tier_scores")
        tier_scores = {}

    failing_tasks = scored.get("failing_tasks")
    if not isinstance(failing_tasks, list):
        failures.append("missing failing_tasks")
        failing_tasks = []

    if failing_tasks:
        failures.append("one or more tasks failed per-task minimum band")

    tier_thresholds = policy.get("tier_min_avg_score", {})
    if not isinstance(tier_thresholds, dict):
        tier_thresholds = {}
    for tier, min_avg in tier_thresholds.items():
        tier_payload = tier_scores.get(str(tier))
        if not isinstance(tier_payload, dict):
            failures.append(f"missing aggregate tier score for tier {tier}")
            continue
        avg_score = float(tier_payload.get("avg_score", 0.0) or 0.0)
        if avg_score < float(min_avg):
            failures.append(f"tier {tier} avg_score {avg_score:.3f} < required {float(min_avg):.3f}")

    overall_avg_score = float(scored.get("overall_avg_score", 0.0) or 0.0)
    overall_min = float(policy.get("overall_min_avg_score", 0.0) or 0.0)
    if overall_avg_score < overall_min:
        failures.append(f"overall_avg_score {overall_avg_score:.3f} < required {overall_min:.3f}")

    result = {
        "ok": len(failures) == 0,
        "overall_avg_score": overall_avg_score,
        "per_task_count": len(per_task),
        "tier_count": len(tier_scores),
        "failures": failures,
    }
    return result


def main() -> int:
    args = _parse_args()
    scored = _load_json(Path(args.scored_report))
    policy = _load_json(Path(args.policy))
    if not isinstance(scored, dict):
        raise SystemExit("Scored report must be a JSON object.")
    if not isinstance(policy, dict):
        raise SystemExit("Policy must be a JSON object.")

    result = evaluate_gate(scored=scored, policy=policy)
    rendered = json.dumps(result, indent=2)
    print(rendered)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    if args.require_thresholds and not result["ok"]:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
