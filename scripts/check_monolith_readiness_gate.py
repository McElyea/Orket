from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check monolith readiness gate against matrix artifact thresholds."
    )
    parser.add_argument(
        "--matrix",
        default="benchmarks/results/monolith_variant_matrix.json",
        help="Path to monolith variant matrix artifact.",
    )
    parser.add_argument("--min-pass-rate", type=float, default=0.85)
    parser.add_argument("--max-runtime-failure-rate", type=float, default=0.20)
    parser.add_argument("--max-reviewer-rejection-rate", type=float, default=0.40)
    parser.add_argument("--min-executed-entries", type=int, default=2)
    return parser.parse_args()


def _load_artifact(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Matrix artifact not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid matrix artifact JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"Invalid matrix artifact structure: {path}")
    return payload


def aggregate_metrics(entries: List[Dict[str, Any]]) -> Dict[str, float]:
    if not entries:
        return {
            "pass_rate": 0.0,
            "runtime_failure_rate": 1.0,
            "reviewer_rejection_rate": 1.0,
        }

    pass_rate = 0.0
    runtime_failure_rate = 0.0
    reviewer_rejection_rate = 0.0
    for entry in entries:
        summary = entry.get("summary", {})
        pass_rate += float(summary.get("pass_rate", 0.0) or 0.0)
        runtime_failure_rate += float(summary.get("runtime_failure_rate", 1.0) or 1.0)
        reviewer_rejection_rate += float(summary.get("reviewer_rejection_rate", 1.0) or 1.0)

    n = float(len(entries))
    return {
        "pass_rate": pass_rate / n,
        "runtime_failure_rate": runtime_failure_rate / n,
        "reviewer_rejection_rate": reviewer_rejection_rate / n,
    }


def main() -> int:
    args = _parse_args()
    artifact = _load_artifact(Path(args.matrix))
    entries = artifact.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit("Invalid matrix artifact: entries must be a list.")

    executed = [entry for entry in entries if bool(entry.get("executed"))]
    if len(executed) < int(args.min_executed_entries):
        raise SystemExit(
            f"Monolith readiness gate failed: executed entries {len(executed)} "
            f"< required {int(args.min_executed_entries)}."
        )

    metrics = aggregate_metrics(executed)
    failures: List[str] = []
    if metrics["pass_rate"] < float(args.min_pass_rate):
        failures.append(
            f"pass_rate {metrics['pass_rate']:.3f} < min_pass_rate {float(args.min_pass_rate):.3f}"
        )
    if metrics["runtime_failure_rate"] > float(args.max_runtime_failure_rate):
        failures.append(
            "runtime_failure_rate "
            f"{metrics['runtime_failure_rate']:.3f} > max_runtime_failure_rate {float(args.max_runtime_failure_rate):.3f}"
        )
    if metrics["reviewer_rejection_rate"] > float(args.max_reviewer_rejection_rate):
        failures.append(
            "reviewer_rejection_rate "
            f"{metrics['reviewer_rejection_rate']:.3f} > max_reviewer_rejection_rate {float(args.max_reviewer_rejection_rate):.3f}"
        )

    report = {
        "ok": len(failures) == 0,
        "executed_entries": len(executed),
        "metrics": metrics,
        "recommended_default_builder_variant": artifact.get("recommended_default_builder_variant"),
        "failures": failures,
    }
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
