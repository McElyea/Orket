from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class MatrixCombo:
    builder_variant: str
    project_surface_profile: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or plan the monolith variant matrix (builder variant x project profile)."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
        help="Models passed to run_live_acceptance_loop.",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--builder-variants",
        nargs="+",
        default=["coder", "architect"],
        help="Builder variants to test.",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["backend_only", "api_vue"],
        help="Project surface profiles to test.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute live acceptance loop per combination. Default is plan-only.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/monolith_variant_matrix.json",
        help="Output artifact path.",
    )
    return parser.parse_args()


def build_combos(builder_variants: List[str], profiles: List[str]) -> List[MatrixCombo]:
    return [
        MatrixCombo(builder_variant=str(builder).strip(), project_surface_profile=str(profile).strip())
        for builder in builder_variants
        for profile in profiles
        if str(builder).strip() and str(profile).strip()
    ]


def _run_command(cmd: List[str], env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def summarize_report(report: Dict[str, Any]) -> Dict[str, Any]:
    completion_by_model = report.get("completion_by_model", {})
    run_count = int(report.get("run_count", 0) or 0)
    passed = 0
    failed = 0
    for stats in completion_by_model.values():
        if not isinstance(stats, dict):
            continue
        passed += int(stats.get("passed", 0) or 0)
        failed += int(stats.get("failed", 0) or 0)

    runtime_failures = int(report.get("pattern_counters", {}).get("runtime_verifier_failures", 0) or 0)
    guard_retries = int(report.get("pattern_counters", {}).get("guard_retry_scheduled", 0) or 0)
    denominator = max(1, run_count)
    return {
        "run_count": run_count,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / denominator,
        "runtime_failure_rate": runtime_failures / denominator,
        "reviewer_rejection_rate": guard_retries / denominator,
    }


def run_matrix_combo(combo: MatrixCombo, args: argparse.Namespace) -> Dict[str, Any]:
    base_env = os.environ.copy()
    base_env["ORKET_ARCHITECTURE_MODE"] = "force_monolith"
    base_env["ORKET_FRONTEND_FRAMEWORK_MODE"] = "force_vue"
    base_env["ORKET_SMALL_PROJECT_BUILDER_VARIANT"] = combo.builder_variant
    base_env["ORKET_PROJECT_SURFACE_PROFILE"] = combo.project_surface_profile

    entry: Dict[str, Any] = {
        "builder_variant": combo.builder_variant,
        "project_surface_profile": combo.project_surface_profile,
        "executed": bool(args.execute),
        "loop_exit_code": None,
        "report_exit_code": None,
        "summary": {
            "run_count": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": 0.0,
            "runtime_failure_rate": 0.0,
            "reviewer_rejection_rate": 0.0,
        },
    }

    if not args.execute:
        return entry

    loop_cmd = [
        "python",
        "-m",
        "scripts.run_live_acceptance_loop",
        "--models",
        *args.models,
        "--iterations",
        str(args.iterations),
    ]
    loop_res = _run_command(loop_cmd, base_env)
    entry["loop_exit_code"] = int(loop_res.returncode)

    with tempfile.TemporaryDirectory(prefix="orket_matrix_") as temp_dir:
        out_path = Path(temp_dir) / "patterns.json"
        report_cmd = [
            "python",
            "scripts/report_live_acceptance_patterns.py",
            "--out",
            str(out_path),
        ]
        report_res = _run_command(report_cmd, base_env)
        entry["report_exit_code"] = int(report_res.returncode)
        report = _load_json(out_path)
        entry["summary"] = summarize_report(report)

    return entry


def choose_default_variant(entries: List[Dict[str, Any]]) -> str:
    executed_entries = [entry for entry in entries if entry.get("executed")]
    if not executed_entries:
        return "coder"
    scored = sorted(
        executed_entries,
        key=lambda entry: (
            float(entry.get("summary", {}).get("pass_rate", 0.0)),
            -float(entry.get("summary", {}).get("runtime_failure_rate", 1.0)),
            -float(entry.get("summary", {}).get("reviewer_rejection_rate", 1.0)),
        ),
        reverse=True,
    )
    return str(scored[0].get("builder_variant") or "coder")


def main() -> int:
    args = _parse_args()
    combos = build_combos(args.builder_variants, args.profiles)
    results = [run_matrix_combo(combo, args) for combo in combos]
    artifact = {
        "schema_version": "v1",
        "execute_mode": bool(args.execute),
        "models": list(args.models),
        "iterations": int(args.iterations),
        "entries": results,
        "recommended_default_builder_variant": choose_default_variant(results),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
