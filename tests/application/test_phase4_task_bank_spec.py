from __future__ import annotations

import json
from pathlib import Path


def _load_tasks() -> list[dict]:
    path = Path("benchmarks/task_bank/v1/tasks.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_phase4_tasks_have_instruction_specs() -> None:
    tasks = _load_tasks()
    phase4_tasks = [task for task in tasks if 1 <= int(task["id"]) <= 60]
    assert len(phase4_tasks) == 60
    assert all(isinstance(task.get("instruction"), str) and task["instruction"].strip() for task in phase4_tasks)


def test_tier3_fault_injection_contract_has_required_scenarios() -> None:
    tasks = _load_tasks()
    tier3_tasks = [task for task in tasks if task["tier"] == 3]
    required = {"timeout", "partial_write", "malformed_input", "interrupted_run", "retry_path"}
    assert len(tier3_tasks) == 25

    for task in tier3_tasks:
        scenarios = set(task["acceptance_contract"].get("fault_injection_scenarios", []))
        assert required.issubset(scenarios)
