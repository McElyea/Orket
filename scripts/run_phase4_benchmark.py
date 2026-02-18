from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 4 benchmark tasks (001-060) in one command.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--venue", default="standard")
    parser.add_argument("--flow", default="default")
    parser.add_argument(
        "--runner-template",
        default="python scripts/orchestration_runner.py --task {task_file} --venue {venue} --flow {flow} --run-dir {run_dir}",
    )
    parser.add_argument("--raw-out", default="benchmarks/results/phase4_determinism_report.json")
    parser.add_argument("--scored-out", default="benchmarks/results/phase4_scored_report.json")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.scored_out).parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python",
        "scripts/run_benchmark_suite.py",
        "--task-bank",
        args.task_bank,
        "--policy",
        args.policy,
        "--runs",
        str(args.runs),
        "--venue",
        args.venue,
        "--flow",
        args.flow,
        "--runner-template",
        args.runner_template,
        "--task-id-min",
        "1",
        "--task-id-max",
        "60",
        "--raw-out",
        args.raw_out,
        "--scored-out",
        args.scored_out,
    ]
    result = subprocess.run(cmd, check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
