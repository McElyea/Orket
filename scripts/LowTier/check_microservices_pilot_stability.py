from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check if microservices pilot is stable across consecutive architecture pilot artifacts."
    )
    parser.add_argument(
        "--artifacts",
        nargs="+",
        required=True,
        help="Ordered architecture pilot matrix artifacts (oldest -> newest).",
    )
    parser.add_argument(
        "--required-consecutive",
        type=int,
        default=2,
        help="Required number of consecutive stable artifacts from the tail.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/microservices_pilot_stability_check.json",
        help="Output JSON artifact path.",
    )
    parser.add_argument(
        "--require-stable",
        action="store_true",
        help="Exit non-zero if stability criteria are not met.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def _check_artifact(payload: Dict[str, Any]) -> Dict[str, Any]:
    comparison = payload.get("comparison") or {}
    available = bool(comparison.get("available"))
    failures: List[str] = []
    if not available:
        failures.append("comparison unavailable")
        return {"stable": False, "failures": failures}

    pass_delta = float(comparison.get("pass_rate_delta_microservices_minus_monolith", 0.0) or 0.0)
    runtime_delta = float(comparison.get("runtime_failure_rate_delta_microservices_minus_monolith", 0.0) or 0.0)
    reviewer_delta = float(comparison.get("reviewer_rejection_rate_delta_microservices_minus_monolith", 0.0) or 0.0)

    if pass_delta < 0.0:
        failures.append(f"pass_rate_delta {pass_delta:.3f} < 0.000")
    if runtime_delta > 0.0:
        failures.append(f"runtime_failure_rate_delta {runtime_delta:.3f} > 0.000")
    if reviewer_delta > 0.0:
        failures.append(f"reviewer_rejection_rate_delta {reviewer_delta:.3f} > 0.000")

    return {
        "stable": len(failures) == 0,
        "comparison": {
            "pass_rate_delta_microservices_minus_monolith": pass_delta,
            "runtime_failure_rate_delta_microservices_minus_monolith": runtime_delta,
            "reviewer_rejection_rate_delta_microservices_minus_monolith": reviewer_delta,
        },
        "failures": failures,
    }


def evaluate_pilot_stability(artifacts: List[Dict[str, Any]], required_consecutive: int) -> Dict[str, Any]:
    checks = [_check_artifact(item) for item in artifacts]
    tail = checks[-required_consecutive:] if required_consecutive > 0 else []
    consecutive_ok = len(tail) == required_consecutive and all(bool(item.get("stable")) for item in tail)
    failures: List[str] = []
    if len(tail) < required_consecutive:
        failures.append(
            f"insufficient artifacts for required_consecutive={required_consecutive} (have {len(tail)})"
        )
    else:
        for idx, item in enumerate(tail):
            if not bool(item.get("stable")):
                reasons = ", ".join(item.get("failures", [])) or "unknown"
                failures.append(f"tail_index={idx} unstable: {reasons}")

    return {
        "stable": consecutive_ok,
        "required_consecutive": int(required_consecutive),
        "artifact_count": len(artifacts),
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    args = _parse_args()
    artifact_paths = [Path(value) for value in args.artifacts if str(value).strip()]
    artifacts = [_load_json(path) for path in artifact_paths]
    result = evaluate_pilot_stability(artifacts, int(args.required_consecutive))
    result["artifact_paths"] = [str(path) for path in artifact_paths]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

    if bool(args.require_stable) and not bool(result.get("stable")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
