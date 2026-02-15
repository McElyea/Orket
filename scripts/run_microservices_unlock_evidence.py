from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import List


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run unlock evidence pipeline: matrix execute + live report + unlock checker."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
        help="Models for matrix and live acceptance loop.",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--matrix-out",
        default="benchmarks/results/monolith_variant_matrix.json",
    )
    parser.add_argument(
        "--live-report-out",
        default="benchmarks/results/live_acceptance_patterns.json",
    )
    parser.add_argument(
        "--unlock-out",
        default="benchmarks/results/microservices_unlock_check.json",
    )
    parser.add_argument(
        "--require-unlocked",
        action="store_true",
        help="Fail if unlock criteria are not met.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing.",
    )
    return parser.parse_args()


def build_command_plan(args: argparse.Namespace) -> List[List[str]]:
    matrix_cmd = [
        "python",
        "scripts/run_monolith_variant_matrix.py",
        "--execute",
        "--models",
        *list(args.models),
        "--iterations",
        str(args.iterations),
        "--out",
        str(args.matrix_out),
    ]
    live_loop_cmd = [
        "python",
        "-m",
        "scripts.run_live_acceptance_loop",
        "--models",
        *list(args.models),
        "--iterations",
        str(args.iterations),
    ]
    report_cmd = [
        "python",
        "scripts/report_live_acceptance_patterns.py",
        "--matrix",
        str(args.matrix_out),
        "--out",
        str(args.live_report_out),
    ]
    unlock_cmd = [
        "python",
        "scripts/check_microservices_unlock.py",
        "--matrix",
        str(args.matrix_out),
        "--readiness-policy",
        "model/core/contracts/monolith_readiness_policy.json",
        "--unlock-policy",
        "model/core/contracts/microservices_unlock_policy.json",
        "--live-report",
        str(args.live_report_out),
        "--out",
        str(args.unlock_out),
    ]
    if bool(args.require_unlocked):
        unlock_cmd.append("--require-unlocked")
    return [matrix_cmd, live_loop_cmd, report_cmd, unlock_cmd]


def _run(cmd: List[str]) -> int:
    print("$ " + " ".join(cmd))
    completed = subprocess.run(cmd, check=False)
    return int(completed.returncode)


def main() -> int:
    args = _parse_args()
    Path(args.matrix_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.live_report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.unlock_out).parent.mkdir(parents=True, exist_ok=True)
    plan = build_command_plan(args)

    if args.dry_run:
        for cmd in plan:
            print("$ " + " ".join(cmd))
        return 0

    for cmd in plan:
        code = _run(cmd)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
