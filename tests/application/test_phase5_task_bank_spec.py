from __future__ import annotations

import json
from pathlib import Path


def _load_tasks() -> list[dict]:
    path = Path("benchmarks/task_bank/v1/tasks.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase5_tasks_have_explicit_instruction_specs() -> None:
    tasks = _load_tasks()
    phase5_tasks = [task for task in tasks if 61 <= int(task["id"]) <= 100]

    assert len(phase5_tasks) == 40
    assert all(isinstance(task.get("instruction"), str) and task["instruction"].strip() for task in phase5_tasks)


def test_tier6_tasks_define_convergence_metrics_contract() -> None:
    tasks = _load_tasks()
    tier6_tasks = [task for task in tasks if task["tier"] == 6]

    assert len(tier6_tasks) == 5
    for task in tier6_tasks:
        acceptance = task["acceptance_contract"]
        assert "convergence_metrics.json" in acceptance["required_artifacts"]
        metrics = acceptance.get("convergence_metrics")
        assert isinstance(metrics, dict)
        assert isinstance(metrics.get("attempts_to_pass"), str) and metrics["attempts_to_pass"].strip()
        assert isinstance(metrics.get("drift_rate"), str) and metrics["drift_rate"].strip()
