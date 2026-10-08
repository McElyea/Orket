"""Shared current-bank admission and truthful workload exits for live suites."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from scripts.benchmarks.determinism_cli import parse_invocation
from scripts.benchmarks.task_acceptance import task_acceptance_definition

ROOT = Path(__file__).resolve().parents[2]
LIVE_TASK_BANK = "benchmarks/task_bank/v2_realworld/tasks.json"


def parse_args(kind: str, argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run current executable tasks through the live {kind} path.")
    parser.add_argument("--task-bank", default=LIVE_TASK_BANK)
    parser.add_argument("--policy", default="model/core/contracts/benchmark_scoring_policy.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--require-score", action="store_true", help="Also require the unchanged scoring-policy gate.")
    parser.add_argument("--runtime-target", "--venue", dest="runtime_target", default="local-hardware")
    parser.add_argument("--execution-mode", "--flow", dest="execution_mode", default="live-card")
    parser.add_argument("--task-id-min", type=int, default=0)
    parser.add_argument("--task-id-max", type=int, default=0, help="Inclusive upper ID; zero selects the whole bank.")
    parser.add_argument("--raw-out", default=f"benchmarks/staging/General/live_{kind}_suite.json")
    parser.add_argument("--scored-out", default=f"benchmarks/staging/General/live_{kind}_suite_scored.json")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*", args.model):
        parser.error("--model must be a nonempty provider model identifier without whitespace or command delimiters")
    return args


def harness_arguments(args: argparse.Namespace, kind: str) -> list[str]:
    runner = ROOT / f"scripts/benchmarks/live_{kind}_benchmark_runner.py"
    template = (f'"{Path(sys.executable).as_posix()}" "{runner.as_posix()}" --model "{args.model}" --task "{{task_file}}" '
                '--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir "{run_dir}"')
    return ["--task-bank", args.task_bank, "--runs", str(args.runs),
            "--runtime-target", args.runtime_target, "--execution-mode", args.execution_mode,
            "--runner-template", template, "--artifact-glob", "live_runner_output.log",
            "--task-id-min", str(args.task_id_min), "--task-id-max", str(args.task_id_max),
            "--output", args.raw_out]


def workload_failures(report: dict) -> list[str]:
    """Recorder success is separate from completion of every requested task run."""
    details = report["details"]
    if not details or len(details) != report["total_tasks"]:
        raise ValueError("Live suite report has incomplete task coverage")
    failures = []
    for identifier, detail in details.items():
        runs = detail["runs"]
        if len(runs) != report["runs_per_task"] or any(run["exit_code"] != 0 for run in runs):
            failures.append(identifier)
    return failures


def _run(arguments: list[str]) -> None:
    result = subprocess.run([sys.executable, *arguments], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)


def main(kind: str, argv: list[str] | None = None) -> int:
    args = parse_args(kind, argv)
    for name in ("task_bank", "policy", "raw_out", "scored_out"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    arguments = harness_arguments(args, kind)
    _, tasks = parse_invocation(arguments)
    try:
        for task in tasks:
            task_acceptance_definition(task)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Live suite oracle preflight failed for task {task['id']}: {exc}", file=sys.stderr)
        return 2
    _run([str(ROOT / "scripts/benchmarks/run_determinism_harness.py"), *arguments])
    _run([str(ROOT / "scripts/benchmarks/score_benchmark_run.py"), "--report", args.raw_out,
          "--task-bank", args.task_bank, "--policy", args.policy, "--out", args.scored_out])
    report = json.loads(Path(args.raw_out).read_text(encoding="utf-8"))
    scored = json.loads(Path(args.scored_out).read_text(encoding="utf-8"))
    failed = workload_failures(report)
    print(json.dumps({"tasks": report["total_tasks"], "workload_failures": failed,
                      "scoring_failures": scored["failing_tasks"], "raw_report": args.raw_out,
                      "scored_report": args.scored_out,
                      "comparison_scope": "runner stdout and declared log artifacts",
                      "runner_output_repeatability": report["determinism_rate"] if report["determinism_rate_valid"] else None}))
    return 1 if failed or (args.require_score and scored["failing_tasks"]) else 0
