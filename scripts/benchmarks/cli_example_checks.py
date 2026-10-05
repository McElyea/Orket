"""Keep CLI correctness separate from bounded, observed repeatability."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def _observed_runs(target: Path, args: list, root: Path) -> tuple[tuple, tuple]:
    command = [sys.executable, str(target), *[str(value) for value in args]]
    results = [subprocess.run(command, cwd=str(root), capture_output=True, text=True,
                              check=False, timeout=5) for _ in range(2)]
    return tuple((r.returncode, r.stdout, r.stderr) for r in results)


def cli_example_checks(evaluation: dict[str, Any], run_dir: Path | None) -> list[dict[str, Any]]:
    examples = evaluation.get("examples") or []
    entrypoint = str(evaluation.get("entrypoint", "agent_output/main.py")).strip() or "agent_output/main.py"
    unavailable = ("run_dir missing for cli_examples evaluation" if run_dir is None else
                   "evaluation.examples missing" if not isinstance(examples, list) or not examples else
                   f"missing entrypoint: {entrypoint}" if not (run_dir / entrypoint).is_file() else "")
    if unavailable:
        return [{"name": "cli_example_cases_pass", "passed": False, "detail": unavailable}]
    assert run_dir is not None
    mismatches, incomplete, differences = [], [], []
    observed = 0
    for index, case in enumerate(examples):
        if not isinstance(case, dict) or not isinstance(case.get("args", []), list):
            incomplete.append(f"invalid case or argument list at index {index}")
            continue
        try:
            first, second = _observed_runs(run_dir / entrypoint, case.get("args", []), run_dir)
        except (subprocess.TimeoutExpired, OSError) as exc:
            incomplete.append(f"cli example not fully observed at index {index}: {type(exc).__name__}")
            continue
        observed += 1
        if first != second:
            differences.append(f"different CLI outputs at index {index}")
        expected = (int(case.get("expected_exit_code", 0)), str(case.get("expected_stdout", "")),
                    str(case.get("expected_stderr", "")))
        for execution, values in enumerate((first, second), 1):
            for label, actual, wanted in zip(("exit", "stdout", "stderr"), values, expected, strict=True):
                if actual != wanted:
                    mismatches.append(f"{label} mismatch at index {index}, execution {execution}: expected={wanted!r} actual={actual!r}")
                    break
    correctness_errors = [*incomplete, *mismatches]
    replay_errors = [*incomplete, *differences]
    return [
        {"name": "cli_example_cases_pass", "passed": not correctness_errors,
         "detail": "; ".join(correctness_errors) if correctness_errors else "all cli examples passed"},
        {"name": "cli_examples_deterministic_replay", "passed": not replay_errors,
         "detail": "; ".join(replay_errors) if replay_errors else
                   f"matching outputs in two observed executions of each of {observed} cases; correctness is separate",
         "observed_cases": observed, "declared_cases": len(examples), "complete": observed == len(examples)},
    ]
