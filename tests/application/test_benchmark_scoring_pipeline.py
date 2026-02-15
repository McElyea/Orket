from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_report_for_tiers() -> dict[str, Any]:
    details: dict[str, Any] = {}
    for tier in range(1, 7):
        task_id = f"{tier:03d}"
        details[task_id] = {
            "tier": tier,
            "unique_hashes": 1,
            "deterministic": True,
            "runs": [{"run_index": 1, "exit_code": 0, "hash": f"h{tier}"}],
        }
    return {
        "task_bank": "benchmarks/task_bank/v1/tasks.json",
        "venue": "standard",
        "flow": "default",
        "runs_per_task": 1,
        "details": details,
    }


def test_score_report_emits_per_task_and_tier_aggregates() -> None:
    score_module = _load_script_module("score_benchmark_run_a", "scripts/score_benchmark_run.py")
    policy = json.loads(Path("model/core/contracts/benchmark_scoring_policy.json").read_text(encoding="utf-8"))
    report = _fake_report_for_tiers()

    tasks_by_id = {task_id: {"id": task_id, "tier": int(task_id)} for task_id in report["details"].keys()}
    scored = score_module.score_report(report_payload=report, tasks_by_id=tasks_by_id, policy=policy)

    assert isinstance(scored["per_task_scores"], dict)
    assert len(scored["per_task_scores"]) == 6
    assert isinstance(scored["aggregate_tier_scores"], dict)
    assert set(scored["aggregate_tier_scores"].keys()) == {"1", "2", "3", "4", "5", "6"}
    assert scored["failing_tasks"] == []


def test_scoring_gate_fails_when_metadata_missing() -> None:
    gate_module = _load_script_module("check_benchmark_scoring_gate_a", "scripts/check_benchmark_scoring_gate.py")
    policy = json.loads(Path("model/core/contracts/benchmark_scoring_policy.json").read_text(encoding="utf-8"))

    result = gate_module.evaluate_gate(scored={"overall_avg_score": 4.9}, policy=policy)
    assert result["ok"] is False
    assert "missing per_task_scores" in result["failures"]
    assert "missing aggregate_tier_scores" in result["failures"]


def test_scoring_gate_passes_for_good_report() -> None:
    score_module = _load_script_module("score_benchmark_run_b", "scripts/score_benchmark_run.py")
    gate_module = _load_script_module("check_benchmark_scoring_gate_b", "scripts/check_benchmark_scoring_gate.py")
    policy = json.loads(Path("model/core/contracts/benchmark_scoring_policy.json").read_text(encoding="utf-8"))
    report = _fake_report_for_tiers()
    tasks_by_id = {task_id: {"id": task_id, "tier": int(task_id)} for task_id in report["details"].keys()}
    scored = score_module.score_report(report_payload=report, tasks_by_id=tasks_by_id, policy=policy)

    result = gate_module.evaluate_gate(scored=scored, policy=policy)
    assert result["ok"] is True
