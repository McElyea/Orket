from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score benchmark determinism runs using tier-aware policy.")
    parser.add_argument("--report", default="benchmarks/results/determinism_report.json")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--out", default="benchmarks/results/benchmark_scored_report.json")
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_tasks_by_id(task_bank_path: Path) -> dict[str, dict[str, Any]]:
    tasks = _load_json(task_bank_path)
    if not isinstance(tasks, list):
        raise ValueError("Task bank must be a JSON array.")
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "").strip()
        if task_id:
            by_id[task_id] = task
    return by_id


def _score_value(success_rate: float, determinism_rate: float) -> float:
    # Weight correctness/execution more heavily than output stability.
    return round((success_rate * 3.0) + (determinism_rate * 2.0), 3)


def _score_to_band(score: float, score_bands: dict[str, float]) -> int:
    if score >= float(score_bands["excellent_min"]):
        return 5
    if score >= float(score_bands["good_min"]):
        return 4
    if score >= float(score_bands["adequate_min"]):
        return 3
    if score >= float(score_bands["poor_min"]):
        return 2
    if score >= float(score_bands["failed_min"]):
        return 1
    return 0


def _task_reason_codes(success_rate: float, unique_hashes: int, deterministic: bool) -> list[str]:
    reasons: list[str] = []
    if success_rate < 1.0:
        reasons.append("non_zero_exit_detected")
    if unique_hashes > 1:
        reasons.append("hash_drift_detected")
    if deterministic:
        reasons.append("deterministic_output")
    return reasons


def score_report(
    report_payload: dict[str, Any],
    tasks_by_id: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    details = report_payload.get("details", {})
    if not isinstance(details, dict):
        raise ValueError("Report details payload must be a JSON object.")

    score_bands = policy.get("score_bands", {})
    if not isinstance(score_bands, dict):
        raise ValueError("Policy score_bands must be a JSON object.")
    per_task_min_band_by_tier = policy.get("per_task_min_band_by_tier", {})
    if not isinstance(per_task_min_band_by_tier, dict):
        raise ValueError("Policy per_task_min_band_by_tier must be a JSON object.")

    per_task_scores: dict[str, Any] = {}
    tier_scores: dict[int, list[float]] = defaultdict(list)
    tier_bands: dict[int, list[int]] = defaultdict(list)
    failing_tasks: list[str] = []
    latency_samples: list[float] = []
    cost_samples: list[float] = []

    for task_id, task_detail in details.items():
        if not isinstance(task_detail, dict):
            continue
        runs = task_detail.get("runs", [])
        if not isinstance(runs, list):
            runs = []

        run_count = len(runs)
        success_count = sum(1 for run in runs if int(run.get("exit_code", 1)) == 0 and isinstance(run, dict))
        success_rate = (success_count / run_count) if run_count else 0.0
        run_latencies = [float(run.get("duration_ms", 0.0) or 0.0) for run in runs if isinstance(run, dict)]
        run_costs = [float(run.get("cost_usd", 0.0) or 0.0) for run in runs if isinstance(run, dict)]
        latency_samples.extend(run_latencies)
        cost_samples.extend(run_costs)

        deterministic = bool(task_detail.get("deterministic"))
        unique_hashes = int(task_detail.get("unique_hashes", max(1, run_count)) or max(1, run_count))
        determinism_rate = 1.0 if deterministic else (1.0 / float(max(1, unique_hashes)))
        numeric_score = _score_value(success_rate=success_rate, determinism_rate=determinism_rate)
        band = _score_to_band(score=numeric_score, score_bands=score_bands)

        task_meta = tasks_by_id.get(task_id, {})
        tier = int(task_detail.get("tier") or task_meta.get("tier") or 0)
        min_band = int(per_task_min_band_by_tier.get(str(tier), 0) or 0)
        passed = band >= min_band
        if not passed:
            failing_tasks.append(task_id)

        per_task_scores[task_id] = {
            "tier": tier,
            "run_count": run_count,
            "success_rate": round(success_rate, 3),
            "unique_hashes": unique_hashes,
            "deterministic": deterministic,
            "avg_latency_ms": round(sum(run_latencies) / len(run_latencies), 3) if run_latencies else 0.0,
            "avg_cost_usd": round(sum(run_costs) / len(run_costs), 6) if run_costs else 0.0,
            "score": numeric_score,
            "band": band,
            "min_required_band": min_band,
            "passed": passed,
            "reason_codes": _task_reason_codes(
                success_rate=success_rate,
                unique_hashes=unique_hashes,
                deterministic=deterministic,
            ),
        }
        if tier > 0:
            tier_scores[tier].append(numeric_score)
            tier_bands[tier].append(band)

    aggregate_tier_scores: dict[str, Any] = {}
    for tier, values in sorted(tier_scores.items()):
        aggregate_tier_scores[str(tier)] = {
            "task_count": len(values),
            "avg_score": round(sum(values) / len(values), 3),
            "avg_band": round(sum(tier_bands[tier]) / len(tier_bands[tier]), 3),
        }

    all_scores = [task["score"] for task in per_task_scores.values()]
    overall_avg_score = round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0

    return {
        "schema_version": "v1",
        "policy_version": str(policy.get("policy_version", "v1")),
        "input_report": report_payload.get("task_bank"),
        "venue": report_payload.get("venue"),
        "flow": report_payload.get("flow"),
        "runs_per_task": report_payload.get("runs_per_task"),
        "determinism_rate": report_payload.get("determinism_rate"),
        "avg_latency_ms": round(sum(latency_samples) / len(latency_samples), 3) if latency_samples else 0.0,
        "avg_cost_usd": round(sum(cost_samples) / len(cost_samples), 6) if cost_samples else 0.0,
        "overall_avg_score": overall_avg_score,
        "per_task_scores": per_task_scores,
        "aggregate_tier_scores": aggregate_tier_scores,
        "failing_tasks": sorted(failing_tasks),
    }


def main() -> int:
    args = _parse_args()
    report_payload = _load_json(Path(args.report))
    if not isinstance(report_payload, dict):
        raise SystemExit("Benchmark report must be a JSON object.")
    policy = _load_json(Path(args.policy))
    if not isinstance(policy, dict):
        raise SystemExit("Policy must be a JSON object.")
    tasks_by_id = _load_tasks_by_id(Path(args.task_bank))
    scored = score_report(report_payload=report_payload, tasks_by_id=tasks_by_id, policy=policy)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scored, indent=2), encoding="utf-8")
    print(json.dumps(scored, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
