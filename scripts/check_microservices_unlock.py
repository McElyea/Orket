from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.check_monolith_readiness_gate import (
        _missing_required_combinations,
        _resolve_thresholds,
        aggregate_metrics,
    )
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent))
    from check_monolith_readiness_gate import (  # type: ignore[no-redef]
        _missing_required_combinations,
        _resolve_thresholds,
        aggregate_metrics,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate whether microservices mode can be unlocked from objective gates."
    )
    parser.add_argument(
        "--matrix",
        default="benchmarks/results/monolith_variant_matrix.json",
        help="Path to monolith variant matrix artifact.",
    )
    parser.add_argument(
        "--readiness-policy",
        default="model/core/contracts/monolith_readiness_policy.json",
        help="Path to monolith readiness policy JSON.",
    )
    parser.add_argument(
        "--unlock-policy",
        default="model/core/contracts/microservices_unlock_policy.json",
        help="Path to microservices unlock policy JSON.",
    )
    parser.add_argument(
        "--live-report",
        default="",
        help="Optional live acceptance report JSON (from report_live_acceptance_patterns.py --out).",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    parser.add_argument(
        "--require-unlocked",
        action="store_true",
        help="Exit non-zero when unlock criteria are not met.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _check_monolith_readiness(
    matrix_payload: Dict[str, Any],
    readiness_policy: Dict[str, Any],
) -> Dict[str, Any]:
    entries = matrix_payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    executed = [entry for entry in entries if bool(entry.get("executed"))]
    thresholds = _resolve_thresholds(
        argparse.Namespace(
            min_pass_rate=0.85,
            max_runtime_failure_rate=0.20,
            max_reviewer_rejection_rate=0.40,
            min_executed_entries=2,
        ),
        readiness_policy,
    )
    failures: List[str] = []
    missing_combinations = _missing_required_combinations(entries, readiness_policy)
    if missing_combinations:
        failures.append(
            "missing required combinations: "
            + ", ".join([f"{builder}/{profile}" for builder, profile in missing_combinations])
        )
    if len(executed) < int(thresholds["min_executed_entries"]):
        failures.append(
            f"executed entries {len(executed)} < required {int(thresholds['min_executed_entries'])}"
        )
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
    return {
        "ok": len(failures) == 0,
        "executed_entries": len(executed),
        "metrics": metrics,
        "failures": failures,
    }


def _matrix_profile_count(entries: List[Dict[str, Any]]) -> int:
    return len(
        {
            str(entry.get("project_surface_profile") or "").strip()
            for entry in entries
            if str(entry.get("project_surface_profile") or "").strip()
        }
    )


def _check_matrix_stability(
    matrix_payload: Dict[str, Any],
    unlock_policy: Dict[str, Any],
) -> Dict[str, Any]:
    entries = matrix_payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    executed = [entry for entry in entries if bool(entry.get("executed"))]
    criteria = (unlock_policy.get("criteria") or {}).get("matrix_stability", {})
    if not isinstance(criteria, dict):
        criteria = {}
    min_executed_entries = int(criteria.get("min_executed_entries", 4))
    min_profiles = int(criteria.get("min_project_surface_profiles", 2))
    min_pass_rate = float(criteria.get("min_pass_rate", 0.8))
    max_runtime_failure_rate = float(criteria.get("max_runtime_failure_rate", 0.25))
    max_reviewer_rejection_rate = float(criteria.get("max_reviewer_rejection_rate", 0.4))

    failures: List[str] = []
    if len(executed) < min_executed_entries:
        failures.append(f"executed entries {len(executed)} < required {min_executed_entries}")
    profile_count = _matrix_profile_count(executed)
    if profile_count < min_profiles:
        failures.append(f"project surface profiles {profile_count} < required {min_profiles}")

    metrics = aggregate_metrics(executed)
    if metrics["pass_rate"] < min_pass_rate:
        failures.append(f"pass_rate {metrics['pass_rate']:.3f} < min_pass_rate {min_pass_rate:.3f}")
    if metrics["runtime_failure_rate"] > max_runtime_failure_rate:
        failures.append(
            f"runtime_failure_rate {metrics['runtime_failure_rate']:.3f} > max_runtime_failure_rate {max_runtime_failure_rate:.3f}"
        )
    if metrics["reviewer_rejection_rate"] > max_reviewer_rejection_rate:
        failures.append(
            "reviewer_rejection_rate "
            f"{metrics['reviewer_rejection_rate']:.3f} > max_reviewer_rejection_rate {max_reviewer_rejection_rate:.3f}"
        )
    return {
        "ok": len(failures) == 0,
        "executed_entries": len(executed),
        "profile_count": profile_count,
        "metrics": metrics,
        "failures": failures,
    }


def _check_governance_stability(
    live_report: Dict[str, Any],
    unlock_policy: Dict[str, Any],
) -> Dict[str, Any]:
    criteria = (unlock_policy.get("criteria") or {}).get("governance_stability", {})
    if not isinstance(criteria, dict):
        criteria = {}
    min_runs = int(criteria.get("min_runs", 2))
    max_terminal_failure_rate = float(criteria.get("max_terminal_failure_rate", 0.25))
    max_guard_retry_rate = float(criteria.get("max_guard_retry_rate", 0.75))
    max_done_chain_mismatch = int(criteria.get("max_done_chain_mismatch", 0))

    run_count = int(live_report.get("run_count", 0) or 0)
    status_counts = live_report.get("session_status_counts", {})
    if not isinstance(status_counts, dict):
        status_counts = {}
    counters = live_report.get("pattern_counters", {})
    if not isinstance(counters, dict):
        counters = {}
    terminal_failure_runs = int(status_counts.get("terminal_failure", 0) or 0)
    guard_retry_total = int(counters.get("guard_retry_scheduled", 0) or 0)
    done_chain_mismatch = int(counters.get("done_chain_mismatch", 0) or 0)
    denom = max(1, run_count)
    terminal_failure_rate = terminal_failure_runs / denom
    guard_retry_rate = guard_retry_total / denom

    failures: List[str] = []
    if run_count < min_runs:
        failures.append(f"run_count {run_count} < required {min_runs}")
    if terminal_failure_rate > max_terminal_failure_rate:
        failures.append(
            f"terminal_failure_rate {terminal_failure_rate:.3f} > max_terminal_failure_rate {max_terminal_failure_rate:.3f}"
        )
    if guard_retry_rate > max_guard_retry_rate:
        failures.append(f"guard_retry_rate {guard_retry_rate:.3f} > max_guard_retry_rate {max_guard_retry_rate:.3f}")
    if done_chain_mismatch > max_done_chain_mismatch:
        failures.append(f"done_chain_mismatch {done_chain_mismatch} > max_done_chain_mismatch {max_done_chain_mismatch}")
    return {
        "ok": len(failures) == 0,
        "run_count": run_count,
        "terminal_failure_rate": terminal_failure_rate,
        "guard_retry_rate": guard_retry_rate,
        "done_chain_mismatch": done_chain_mismatch,
        "failures": failures,
    }


def evaluate_unlock(
    matrix_payload: Dict[str, Any],
    readiness_policy: Dict[str, Any],
    unlock_policy: Dict[str, Any],
    live_report: Dict[str, Any],
) -> Dict[str, Any]:
    criteria = unlock_policy.get("criteria", {})
    if not isinstance(criteria, dict):
        criteria = {}

    criteria_results: Dict[str, Dict[str, Any]] = {}
    failures: List[str] = []

    monolith_required = bool((criteria.get("monolith_readiness_gate") or {}).get("required", True))
    if monolith_required:
        monolith_result = _check_monolith_readiness(matrix_payload, readiness_policy)
    else:
        monolith_result = {"ok": True, "failures": []}
    criteria_results["monolith_readiness_gate"] = monolith_result
    if not monolith_result.get("ok", False):
        failures.extend([f"monolith_readiness_gate: {item}" for item in monolith_result.get("failures", [])])

    matrix_required = bool((criteria.get("matrix_stability") or {}).get("required", True))
    if matrix_required:
        matrix_result = _check_matrix_stability(matrix_payload, unlock_policy)
    else:
        matrix_result = {"ok": True, "failures": []}
    criteria_results["matrix_stability"] = matrix_result
    if not matrix_result.get("ok", False):
        failures.extend([f"matrix_stability: {item}" for item in matrix_result.get("failures", [])])

    governance_required = bool((criteria.get("governance_stability") or {}).get("required", True))
    if governance_required:
        if live_report:
            governance_result = _check_governance_stability(live_report, unlock_policy)
        else:
            governance_result = {
                "ok": False,
                "failures": ["live acceptance report missing (pass --live-report)"],
            }
    else:
        governance_result = {"ok": True, "failures": []}
    criteria_results["governance_stability"] = governance_result
    if not governance_result.get("ok", False):
        failures.extend([f"governance_stability: {item}" for item in governance_result.get("failures", [])])

    return {
        "unlocked": len(failures) == 0,
        "criteria": criteria_results,
        "failures": failures,
        "recommended_default_builder_variant": matrix_payload.get("recommended_default_builder_variant"),
    }


def main() -> int:
    args = _parse_args()
    matrix_payload = _load_json(Path(args.matrix))
    if not matrix_payload:
        raise SystemExit(f"Matrix artifact not found or invalid: {args.matrix}")
    readiness_policy = _load_json(Path(args.readiness_policy))
    unlock_policy = _load_json(Path(args.unlock_policy))
    if not unlock_policy:
        raise SystemExit(f"Unlock policy not found or invalid: {args.unlock_policy}")

    live_report = _load_json(Path(args.live_report)) if args.live_report else {}
    result = evaluate_unlock(matrix_payload, readiness_policy, unlock_policy, live_report)
    rendered = json.dumps(result, indent=2)
    print(rendered)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    if args.require_unlocked and not result.get("unlocked", False):
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
