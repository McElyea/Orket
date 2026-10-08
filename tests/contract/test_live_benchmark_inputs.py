"""Contract: live admission retains executable oracles and task-specific semantics."""
import json
from pathlib import Path

import pytest

from scripts.benchmarks.determinism_cli import parse_invocation
from scripts.benchmarks.live_card_benchmark_runner import _build_epic
from scripts.benchmarks.live_suite import harness_arguments, parse_args, workload_failures
from scripts.benchmarks.task_acceptance import declare_task_acceptance, task_acceptance_definition

pytestmark = pytest.mark.contract
TASKS = json.loads(Path("benchmarks/task_bank/v2_realworld/tasks.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", ["card", "rock"])
def test_both_live_defaults_select_all_eighty_executable_tasks(kind):
    _, tasks = parse_invocation(harness_arguments(parse_args(kind, []), kind))
    assert [task["id"] for task in tasks] == [f"{index:03d}" for index in range(1, 81)]
    for task in tasks:
        assert task_acceptance_definition(task).cases


@pytest.mark.parametrize("identifier", ["010", "032", "050", "055", "060", "073"])
def test_function_prompt_preserves_specific_order_and_exposes_constraints(tmp_path, identifier):
    task = next(task for task in TASKS if task["id"] == identifier)
    epic = _build_epic(task, "task_context.json", "result.md")
    declare_task_acceptance(epic, task, tmp_path)
    summary = epic["issues"][0]["summary"]
    assert "Deterministic does not mean sorted" in summary
    assert "sort each inner group" not in summary
    assert "normalize to deterministic ordering" not in epic["issues"][0]["note"]
    assert json.dumps(task["constraints"]) in summary
    assert json.dumps(task["acceptance_contract"]["quality_forbidden_keywords"]) in summary


@pytest.mark.parametrize("runs,expected", [([{"exit_code": 0}], []),
                                          ([{"exit_code": 1}], ["001"]), ([], ["001"])])
def test_recorder_completion_does_not_hide_failed_or_missing_workload_runs(runs, expected):
    assert workload_failures({"total_tasks": 1, "runs_per_task": 1,
                              "details": {"001": {"runs": runs}}}) == expected


def test_missing_suite_details_cannot_pass():
    with pytest.raises(ValueError, match="incomplete task coverage"):
        workload_failures({"total_tasks": 1, "runs_per_task": 1, "details": {}})
