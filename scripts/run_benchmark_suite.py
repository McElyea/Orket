from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark determinism harness and scoring in one command.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--runtime-target", "--venue", dest="runtime_target", default="standard")
    parser.add_argument("--execution-mode", "--flow", dest="execution_mode", default="default")
    parser.add_argument("--runner-template", required=True)
    parser.add_argument("--task-limit", type=int, default=0)
    parser.add_argument("--task-id-min", type=int, default=0)
    parser.add_argument("--task-id-max", type=int, default=0)
    parser.add_argument("--raw-out", default="benchmarks/results/benchmark_determinism_report.json")
    parser.add_argument("--scored-out", default="benchmarks/results/benchmark_scored_report.json")
    parser.add_argument("--memory-trace", default="")
    parser.add_argument("--memory-retrieval-trace", default="")
    parser.add_argument("--memory-check-out", default="benchmarks/results/memory_determinism_check.json")
    parser.add_argument("--memory-compare-left", default="")
    parser.add_argument("--memory-compare-right", default="")
    parser.add_argument("--memory-compare-left-retrieval", default="")
    parser.add_argument("--memory-compare-right-retrieval", default="")
    parser.add_argument("--memory-compare-out", default="benchmarks/results/memory_determinism_compare.json")
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
    if str(args.memory_check_out or "").strip():
        Path(str(args.memory_check_out)).parent.mkdir(parents=True, exist_ok=True)
    if str(args.memory_compare_out or "").strip():
        Path(str(args.memory_compare_out)).parent.mkdir(parents=True, exist_ok=True)

    harness_cmd = [
        "python",
        "scripts/run_determinism_harness.py",
        "--task-bank",
        args.task_bank,
        "--runs",
        str(args.runs),
        "--runtime-target",
        args.runtime_target,
        "--execution-mode",
        args.execution_mode,
        "--runner-template",
        args.runner_template,
        "--output",
        args.raw_out,
    ]
    if args.task_limit > 0:
        harness_cmd.extend(["--task-limit", str(args.task_limit)])
    if args.task_id_min > 0:
        harness_cmd.extend(["--task-id-min", str(args.task_id_min)])
    if args.task_id_max > 0:
        harness_cmd.extend(["--task-id-max", str(args.task_id_max)])
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

    memory_trace = str(args.memory_trace or "").strip()
    memory_retrieval_trace = str(args.memory_retrieval_trace or "").strip()
    if memory_trace:
        check_cmd = [
            "python",
            "scripts/check_memory_determinism.py",
            "--trace",
            memory_trace,
            "--out",
            str(args.memory_check_out),
        ]
        if memory_retrieval_trace:
            check_cmd.extend(["--retrieval-trace", memory_retrieval_trace])
        _run(check_cmd)

    compare_left = str(args.memory_compare_left or "").strip()
    compare_right = str(args.memory_compare_right or "").strip()
    if compare_left and compare_right:
        compare_cmd = [
            "python",
            "scripts/compare_memory_determinism.py",
            "--left",
            compare_left,
            "--right",
            compare_right,
            "--out",
            str(args.memory_compare_out),
        ]
        left_retrieval = str(args.memory_compare_left_retrieval or "").strip()
        right_retrieval = str(args.memory_compare_right_retrieval or "").strip()
        if left_retrieval and right_retrieval:
            compare_cmd.extend(
                [
                    "--left-retrieval",
                    left_retrieval,
                    "--right-retrieval",
                    right_retrieval,
                ]
            )
        _run(compare_cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
