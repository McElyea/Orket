"""Validate benchmark command and selected task inputs before any runner effect."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run benchmark tasks repeatedly and report output drift.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--runtime-target", "--venue", dest="runtime_target", default="standard")
    parser.add_argument("--execution-mode", "--flow", dest="execution_mode", default="default")
    parser.add_argument("--output", default="benchmarks/results/benchmarks/determinism_report.json")
    parser.add_argument(
        "--runner-template", required=True,
        help="Explicit command with {task_file}, {runtime_target}, {execution_mode}, {venue}, {flow}, "
             "{run_dir}, {repo_root}, {workdir}, {seed}, {threads}, {affinity_policy}, {warmup_steps} placeholders.",
    )
    parser.add_argument("--artifact-glob", action="append", default=[], help="Relative artifact globs under run workdir.")
    parser.add_argument("--task-limit", type=int, default=0, help="Optional maximum selected tasks; zero means all.")
    parser.add_argument("--task-id-min", type=int, default=0, help="Inclusive numeric task ID lower bound; zero disables.")
    parser.add_argument("--task-id-max", type=int, default=0, help="Inclusive numeric task ID upper bound; zero disables.")
    parser.add_argument("--seed", type=int, default=0, help="Benchmark seed metadata; zero means unset.")
    parser.add_argument("--threads", type=int, default=0, help="Benchmark thread metadata; zero means unset.")
    parser.add_argument("--affinity-policy", default="", help="CPU affinity policy/mask metadata; empty means unset.")
    parser.add_argument("--warmup-steps", type=int, default=0, help="Warmup step metadata; zero means unset.")
    return parser


def _selected_tasks(args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks = json.loads(Path(args.task_bank).read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("E_BENCHMARK_TASK_BANK_INVALID: expected a JSON array")
    identifiers = set()
    for task in tasks:
        if not isinstance(task, dict) or type(task.get("id")) not in (str, int) or not str(task["id"]).strip():
            raise ValueError("E_BENCHMARK_TASK_INVALID: each task requires a nonempty string or integer id")
        identifier = str(task["id"]).strip()
        if identifier in identifiers:
            raise ValueError("E_BENCHMARK_TASK_ID_DUPLICATE")
        identifiers.add(identifier)
        task["id"] = identifier
    if args.task_id_min > 0:
        tasks = [task for task in tasks if int(task["id"]) >= args.task_id_min]
    if args.task_id_max > 0:
        tasks = [task for task in tasks if int(task["id"]) <= args.task_id_max]
    if args.task_limit > 0:
        tasks = tasks[:args.task_limit]
    if not tasks:
        raise ValueError("E_BENCHMARK_TASK_SET_EMPTY")
    return tasks


def parse_invocation(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[dict[str, Any]]]:
    parser = _argument_parser()
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("E_BENCHMARK_RUN_COUNT_INVALID: --runs must be positive")
    if not args.runner_template.strip():
        parser.error("E_BENCHMARK_RUNNER_REQUIRED: --runner-template cannot be empty")
    if min(args.task_limit, args.task_id_min, args.task_id_max) < 0 or (
            args.task_id_max > 0 and args.task_id_min > args.task_id_max):
        parser.error("E_BENCHMARK_TASK_FILTER_INVALID")
    try:
        tasks = _selected_tasks(args)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(str(error))
    return args, tasks
