from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark tasks 001-100 through live Orket card execution.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--venue", default="local-hardware")
    parser.add_argument("--flow", default="live-card")
    parser.add_argument("--raw-out", default="benchmarks/results/live_card_100_determinism_report.json")
    parser.add_argument("--scored-out", default="benchmarks/results/live_card_100_scored_report.json")
    return parser.parse_args()


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        raise SystemExit(result.returncode)


def main() -> int:
    args = _parse_args()
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.scored_out).parent.mkdir(parents=True, exist_ok=True)

    harness_cmd = [
        "python",
        "scripts/run_determinism_harness.py",
        "--task-bank",
        args.task_bank,
        "--runs",
        str(args.runs),
        "--venue",
        args.venue,
        "--flow",
        args.flow,
        "--runner-template",
        "python scripts/live_card_benchmark_runner.py --task {task_file} --venue {venue} --flow {flow} --run-dir {run_dir}",
        "--artifact-glob",
        "live_runner_output.log",
        "--task-id-min",
        "1",
        "--task-id-max",
        "100",
        "--output",
        args.raw_out,
    ]
    _run(harness_cmd)

    score_cmd = [
        "python",
        "scripts/score_benchmark_run.py",
        "--report",
        args.raw_out,
        "--task-bank",
        args.task_bank,
        "--policy",
        args.policy,
        "--out",
        args.scored_out,
    ]
    _run(score_cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
