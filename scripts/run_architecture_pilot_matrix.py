from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.run_monolith_variant_matrix import summarize_report
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from scripts.run_monolith_variant_matrix import summarize_report


@dataclass(frozen=True)
class PilotCombo:
    architecture_mode: str
    builder_variant: str
    project_surface_profile: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or plan architecture pilot matrix (architecture x builder x project profile)."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
        help="Models passed to run_live_acceptance_loop.",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--architecture-modes",
        nargs="+",
        default=["force_monolith", "force_microservices"],
        help="Architecture modes to test.",
    )
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
        default="benchmarks/results/architecture_pilot_matrix.json",
        help="Output artifact path.",
    )
    return parser.parse_args()


def build_combos(
    architecture_modes: List[str],
    builder_variants: List[str],
    profiles: List[str],
) -> List[PilotCombo]:
    combos: List[PilotCombo] = []
    for mode in architecture_modes:
        normalized_mode = str(mode).strip()
        if not normalized_mode:
            continue
        for builder in builder_variants:
            normalized_builder = str(builder).strip()
            if not normalized_builder:
                continue
            for profile in profiles:
                normalized_profile = str(profile).strip()
                if not normalized_profile:
                    continue
                combos.append(
                    PilotCombo(
                        architecture_mode=normalized_mode,
                        builder_variant=normalized_builder,
                        project_surface_profile=normalized_profile,
                    )
                )
    return combos


def _run_command(cmd: List[str], env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _build_env(combo: PilotCombo) -> Dict[str, str]:
    env = os.environ.copy()
    env["ORKET_ARCHITECTURE_MODE"] = combo.architecture_mode
    env["ORKET_FRONTEND_FRAMEWORK_MODE"] = "force_vue"
    env["ORKET_SMALL_PROJECT_BUILDER_VARIANT"] = combo.builder_variant
    env["ORKET_PROJECT_SURFACE_PROFILE"] = combo.project_surface_profile
    env["ORKET_ENABLE_MICROSERVICES"] = "true" if combo.architecture_mode == "force_microservices" else "false"
    return env


def run_matrix_combo(combo: PilotCombo, args: argparse.Namespace) -> Dict[str, Any]:
    env = _build_env(combo)
    entry: Dict[str, Any] = {
        "architecture_mode": combo.architecture_mode,
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
    loop_res = _run_command(loop_cmd, env)
    entry["loop_exit_code"] = int(loop_res.returncode)

    with tempfile.TemporaryDirectory(prefix="orket_arch_pilot_") as temp_dir:
        out_path = Path(temp_dir) / "patterns.json"
        report_cmd = [
            "python",
            "scripts/report_live_acceptance_patterns.py",
            "--out",
            str(out_path),
        ]
        report_res = _run_command(report_cmd, env)
        entry["report_exit_code"] = int(report_res.returncode)
        entry["summary"] = summarize_report(_load_json(out_path))
    return entry


def _aggregate_by_architecture(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for entry in entries:
        if not entry.get("executed"):
            continue
        mode = str(entry.get("architecture_mode") or "").strip()
        if not mode:
            continue
        buckets.setdefault(mode, []).append(entry)

    result: Dict[str, Dict[str, float]] = {}
    for mode, grouped in buckets.items():
        run_count = sum(int(e.get("summary", {}).get("run_count", 0) or 0) for e in grouped)
        passed = sum(int(e.get("summary", {}).get("passed", 0) or 0) for e in grouped)
        failed = sum(int(e.get("summary", {}).get("failed", 0) or 0) for e in grouped)
        runtime_failure_rate = (
            sum(float(e.get("summary", {}).get("runtime_failure_rate", 0.0) or 0.0) for e in grouped) / max(1, len(grouped))
        )
        reviewer_rejection_rate = (
            sum(float(e.get("summary", {}).get("reviewer_rejection_rate", 0.0) or 0.0) for e in grouped) / max(1, len(grouped))
        )
        result[mode] = {
            "entry_count": float(len(grouped)),
            "run_count": float(run_count),
            "passed": float(passed),
            "failed": float(failed),
            "pass_rate": float(passed) / float(max(1, run_count)),
            "runtime_failure_rate": runtime_failure_rate,
            "reviewer_rejection_rate": reviewer_rejection_rate,
        }
    return result


def _build_comparison(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_arch = _aggregate_by_architecture(entries)
    mono = by_arch.get("force_monolith")
    micro = by_arch.get("force_microservices")
    if not mono or not micro:
        return {"available": False}
    return {
        "available": True,
        "pass_rate_delta_microservices_minus_monolith": float(micro["pass_rate"]) - float(mono["pass_rate"]),
        "runtime_failure_rate_delta_microservices_minus_monolith": float(micro["runtime_failure_rate"])
        - float(mono["runtime_failure_rate"]),
        "reviewer_rejection_rate_delta_microservices_minus_monolith": float(micro["reviewer_rejection_rate"])
        - float(mono["reviewer_rejection_rate"]),
    }


def main() -> int:
    args = _parse_args()
    combos = build_combos(args.architecture_modes, args.builder_variants, args.profiles)
    entries = [run_matrix_combo(combo, args) for combo in combos]
    artifact = {
        "schema_version": "v1",
        "execute_mode": bool(args.execute),
        "models": list(args.models),
        "iterations": int(args.iterations),
        "architecture_modes": list(args.architecture_modes),
        "entries": entries,
        "aggregates": {"by_architecture_mode": _aggregate_by_architecture(entries)},
        "comparison": _build_comparison(entries),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
