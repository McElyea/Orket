"""Integration: benchmark inputs reach native turn preparation with the declared scope."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows.turn_contract_rules import hallucination_scope_diagnostics
from orket.core.cards_runtime_contract import resolve_cards_runtime
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from scripts.benchmarks.live_card_benchmark_runner import _build_epic
from scripts.benchmarks.task_acceptance import declare_task_acceptance
from tests.integration.test_dispatch_input_admission import _dispatch_context

pytestmark = pytest.mark.integration
TASKS = json.loads(Path("benchmarks/task_bank/v2_realworld/tasks.json").read_text(encoding="utf-8"))
CASES = [task for task in TASKS if task["evaluation"]["type"] == "cli_examples" or task["id"] == "060"]


@pytest.mark.asyncio
@pytest.mark.parametrize("task", CASES, ids=lambda task: task["id"])
async def test_native_context_admits_every_required_module_and_task_input(tmp_path, task):
    repo, _, _, orchestrator = await _dispatch_context(tmp_path, SimpleNamespace())
    workspace = orchestrator.workspace

    def prepare():
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "task_context.json").write_text(json.dumps(task), encoding="utf-8")
        epic = _build_epic(task, "task_context.json", "result.md")
        declare_task_acceptance(epic, task, workspace)
        return IssueRecord.model_validate({**epic["issues"][0], "build_id": "build"})

    issue = await asyncio.to_thread(prepare)
    await repo.save(issue)
    issue = await repo.get_by_id(issue.id)
    context = await orchestrator._build_turn_context(
        run_id="scope", issue=issue, seat_name="coder", roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS, selected_model="fixture",
        prompt_metadata={}, prompt_layers={}, cards_runtime=resolve_cards_runtime(issue=issue),
    )
    outputs = task["evaluation"].get("artifact_paths", ["agent_output/main.py"])
    assert context["required_write_paths"] == outputs
    assert context["required_read_paths"] == ["task_context.json"]
    assert set(context["verification_scope"]["workspace"]) == {"task_context.json", *outputs}
    assert "read_file" in context["verification_scope"]["declared_interfaces"]
    assert "agent_output/benchmark_verify.py" not in context["required_write_paths"]
    turn = ExecutionTurn(role="coder", issue_id=issue.id, timestamp=None,
                         tool_calls=[ToolCall("read_file", {"path": "task_context.json"})])
    assert not hallucination_scope_diagnostics(turn, context, lambda _: "")["violations"]
    turn.tool_calls[0].args["path"] = "unrelated-secret.txt"
    violations = hallucination_scope_diagnostics(turn, context, lambda _: "")["violations"]
    assert [row["rule_id"] for row in violations] == ["HALLUCINATION.FILE_NOT_FOUND"]
