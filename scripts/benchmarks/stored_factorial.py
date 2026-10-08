"""Materialize the stored factorial example from the authoritative executable bank."""
import json
from pathlib import Path

from scripts.benchmarks.live_card_benchmark_runner import _build_epic
from scripts.benchmarks.live_suite import LIVE_TASK_BANK
from scripts.benchmarks.task_acceptance import declare_task_acceptance


def prepare_factorial(source: Path, project: Path, workspace: Path) -> dict:
    tasks = json.loads((source / LIVE_TASK_BANK).read_text(encoding="utf-8"))
    task = next(task for task in tasks if task["id"] == "008")
    epic = _build_epic(task, "task_context.json", "benchmark_task_008_output.md")
    epic["name"] = "factorial"
    epic["description"] = "Generated from executable v2 task 008; prepare inputs before running."
    declare_task_acceptance(epic, task, workspace)
    (workspace / "task_context.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    destination = project / "model/core/epics/factorial.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(epic, indent=2) + "\n", encoding="utf-8")
    return epic
