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
    parser.add_argument(
        "--policy",
        default="model/core/contracts/monolith_readiness_policy.json",
        help="Path to readiness policy JSON.",
    )
    parser.add_argument("--min-pass-rate", type=float, default=0.85)
    parser.add_argument("--max-runtime-failure-rate", type=float, default=0.20)
    parser.add_argument("--max-reviewer-rejection-rate", type=float, default=0.40)
    parser.add_argument("--min-executed-entries", type=int, default=2)
    parser.add_argument(
        "--allow-plan-only",
        action="store_true",
        help="Allow validation to pass with zero executed entries if required combinations are present.",
    )
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


def _load_policy(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
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
    def _safe_float(summary: Dict[str, Any], key: str, default: float) -> float:
        value = summary.get(key, default)
        if value is None:
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    for entry in entries:
        summary = entry.get("summary", {})
        if not isinstance(summary, dict):
            summary = {}
        pass_rate += _safe_float(summary, "pass_rate", 0.0)
        runtime_failure_rate += _safe_float(summary, "runtime_failure_rate", 1.0)
        reviewer_rejection_rate += _safe_float(summary, "reviewer_rejection_rate", 1.0)

    n = float(len(entries))
    return {
        "pass_rate": pass_rate / n,
        "runtime_failure_rate": runtime_failure_rate / n,
        "reviewer_rejection_rate": reviewer_rejection_rate / n,
    }


def _combination_key(entry: Dict[str, Any]) -> tuple[str, str]:
    return (
        str(entry.get("builder_variant") or "").strip(),
        str(entry.get("project_surface_profile") or "").strip(),
    )


def _missing_required_combinations(entries: List[Dict[str, Any]], policy: Dict[str, Any]) -> List[tuple[str, str]]:
    required = policy.get("required_combinations", [])
    if not isinstance(required, list):
        return []
    present = {_combination_key(entry) for entry in entries}
    missing: List[tuple[str, str]] = []
    for item in required:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("builder_variant") or "").strip(),
            str(item.get("project_surface_profile") or "").strip(),
        )
        if key[0] and key[1] and key not in present:
            missing.append(key)
    return missing


def _resolve_thresholds(args: argparse.Namespace, policy: Dict[str, Any]) -> Dict[str, float]:
    thresholds = policy.get("thresholds", {})
    if not isinstance(thresholds, dict):
        thresholds = {}
    return {
        "min_pass_rate": float(thresholds.get("min_pass_rate", args.min_pass_rate)),
        "max_runtime_failure_rate": float(
            thresholds.get("max_runtime_failure_rate", args.max_runtime_failure_rate)
        ),
        "max_reviewer_rejection_rate": float(
            thresholds.get("max_reviewer_rejection_rate", args.max_reviewer_rejection_rate)
        ),
        "min_executed_entries": int(thresholds.get("min_executed_entries", args.min_executed_entries)),
    }


def main() -> int:
    args = _parse_args()
    artifact = _load_artifact(Path(args.matrix))
    policy = _load_policy(Path(args.policy))
    thresholds = _resolve_thresholds(args, policy)
    entries = artifact.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit("Invalid matrix artifact: entries must be a list.")

    executed = [entry for entry in entries if bool(entry.get("executed"))]
    missing_combinations = _missing_required_combinations(entries, policy)
    failures: List[str] = []
    if missing_combinations:
        failures.append(
            "missing required combinations: "
            + ", ".join([f"{builder}/{profile}" for builder, profile in missing_combinations])
        )
    if len(executed) < int(thresholds["min_executed_entries"]):
        if not args.allow_plan_only:
            failures.append(
                f"executed entries {len(executed)} < required {int(thresholds['min_executed_entries'])}"
            )
        elif len(executed) == 0:
            report = {
                "ok": len(failures) == 0,
                "executed_entries": len(executed),
                "metrics": {
                    "pass_rate": None,
                    "runtime_failure_rate": None,
                    "reviewer_rejection_rate": None,
                },
                "recommended_default_builder_variant": artifact.get("recommended_default_builder_variant"),
                "failures": failures,
                "mode": "plan_only",
            }
            print(json.dumps(report, indent=2))
            if failures:
                raise SystemExit(1)
            return 0

    metrics = aggregate_metrics(executed)
    if metrics["pass_rate"] < float(thresholds["min_pass_rate"]):
        failures.append(
            f"pass_rate {metrics['pass_rate']:.3f} < min_pass_rate {float(thresholds['min_pass_rate']):.3f}"
        )
    if metrics["runtime_failure_rate"] > float(thresholds["max_runtime_failure_rate"]):
        failures.append(
            "runtime_failure_rate "
            f"{metrics['runtime_failure_rate']:.3f} > max_runtime_failure_rate {float(thresholds['max_runtime_failure_rate']):.3f}"
        )
    if metrics["reviewer_rejection_rate"] > float(thresholds["max_reviewer_rejection_rate"]):
        failures.append(
            "reviewer_rejection_rate "
            f"{metrics['reviewer_rejection_rate']:.3f} > max_reviewer_rejection_rate {float(thresholds['max_reviewer_rejection_rate']):.3f}"
        )

    report = {
        "ok": len(failures) == 0,
        "executed_entries": len(executed),
        "metrics": metrics,
        "recommended_default_builder_variant": artifact.get("recommended_default_builder_variant"),
        "failures": failures,
        "mode": "executed",
    }
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
