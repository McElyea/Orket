"""Real approval denial refuses a resolved step whose current journal is missing."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.core.contracts.turn_tool_dispatch import is_unresolved_tool_dispatch
from orket.core.domain import AttemptState
from tests.helpers.operation_binding import _dump
from tests.helpers.step_journal_opening import (
    PRIOR_READ_PATH,
    physical_tree_state,
    prepare_approval_prior_read_assets,
    remove_journal,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_approval_terminal_transaction import capture_closeout, decide
from tests.integration.test_epic_approval_continuation import (
    ToolApprovalContinuationProvider,
    approval_engine,
    pause,
)
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("deterministic_turn_clock"),
]
APPROVED_OUTPUT = "agent_output/approved.txt"


class PriorReadApprovalProvider(ToolApprovalContinuationProvider):
    async def complete(self, messages):  # type: ignore[no-untyped-def]
        result = await super().complete(messages)
        if '"write_file"' in result.content:
            read = json.dumps({"tool": "read_file", "args": {"path": PRIOR_READ_PATH}}, sort_keys=True)
            result.content = f"```json\n{read}\n```\n" + result.content
        return result


def _record(record_property, observation: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    record_property("approval_step_journal_observation", json.dumps(observation, sort_keys=True))


async def _remove_prior_read_journal(engine, approval) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    run_id = str(approval["control_plane_target_ref"])
    run = await engine.control_plane_execution_repository.get_run_record(run_id=run_id)
    assert run is not None and run.current_attempt_id is not None
    attempt_id = run.current_attempt_id
    approval_payload = approval["payload"]
    assert isinstance(approval_payload, dict)
    assert approval_payload["tool"] == "write_file"
    assert approval_payload["args"]["path"] == APPROVED_OUTPUT
    steps = await engine.control_plane_execution_repository.list_step_records(attempt_id=attempt_id)
    assert len(steps) == 1 and not is_unresolved_tool_dispatch(steps[0])
    step = steps[0]
    step_payload = _dump(step)
    assert step_payload["capability_used"] == "observe"
    assert step_payload["observed_result_classification"] == "tool_succeeded"
    assert step_payload["closure_classification"] == "step_completed"
    assert f"workspace:{PRIOR_READ_PATH}" in step_payload["resources_touched"]
    effects = await engine.control_plane_repository.list_effect_journal_entries(run_id=run_id)
    matching = [row for row in effects if row.attempt_id == attempt_id and row.step_id == step.step_id]
    assert len(effects) == len(matching) == 1
    journal = matching[0]
    removed = await remove_journal(
        engine.control_plane_execution_repository.db_path,
        journal_id=journal.journal_entry_id,
        run_id=run_id,
        attempt_id=attempt_id,
        step_id=step.step_id,
    )
    retained = await engine.control_plane_execution_repository.get_step_record(step_id=step.step_id)
    assert _dump(retained) == step_payload
    assert await engine.control_plane_repository.list_effect_journal_entries(run_id=run_id) == []
    return {"run_id": run_id, "attempt_id": attempt_id, "step": step_payload,
            "removed_journal": removed, "approval_tool": approval_payload["tool"]}


# Layer: integration. Real HTTP denial and existing transaction owner see the corrupted child join.
async def test_approval_denial_refuses_resolved_step_without_current_journal(
    tmp_path: Path, monkeypatch, record_property,
) -> None:
    async with approval_engine(
        tmp_path, monkeypatch, setup=True, provider=PriorReadApprovalProvider(),
        prepare_assets=prepare_approval_prior_read_assets,
    ) as engine:
        approval = await pause(engine)
        fixture = await _remove_prior_read_journal(engine, approval)
        db = engine.control_plane_execution_repository.db_path
        workspace = tmp_path / "workspace"
        before_physical = await physical_tree_state(workspace)
        with monkeypatch.context() as patch:
            captured = capture_closeout(patch, db)
            response = await decide(engine, approval)
        after_logical = await logical_state(db)
        after_physical = await physical_tree_state(workspace)
        after_run = await engine.control_plane_execution_repository.get_run_record(run_id=fixture["run_id"])
        after_attempt = await engine.control_plane_execution_repository.get_attempt_record(
            attempt_id=fixture["attempt_id"]
        )
        after_truth = await engine.control_plane_repository.get_final_truth(run_id=fixture["run_id"])
        observation = {
            "fixture": fixture,
            "response": {"status_code": response.status_code, "text": response.text},
            "terminal_before_logical": captured.get("before"),
            "after_logical": after_logical,
            "before_physical": before_physical,
            "after_physical": after_physical,
            "approved_output": {
                "relative_path": APPROVED_OUTPUT,
                "before_exists": APPROVED_OUTPUT in before_physical["files"],
                "after_exists": APPROVED_OUTPUT in after_physical["files"],
            },
            "after_child": {
                "run": _dump(after_run),
                "attempt": _dump(after_attempt),
                "truth": None if after_truth is None else _dump(after_truth),
            },
        }
        _record(record_property, observation)

        assert response.status_code in {409, 422}, observation
        lowered = response.text.lower()
        assert fixture["run_id"] in response.text and fixture["step"]["step_id"] in response.text
        assert "effect journal" in lowered
        assert observation["terminal_before_logical"] is not None
        assert observation["after_logical"] == observation["terminal_before_logical"]
        assert observation["approved_output"] == {
            "relative_path": APPROVED_OUTPUT, "before_exists": False, "after_exists": False,
        }
        assert observation["before_physical"]["log_write_frontier"] == "settled"
        assert observation["after_physical"] == observation["before_physical"]
        assert observation["after_child"]["run"]["lifecycle_state"] == "executing"
        assert observation["after_child"]["attempt"]["attempt_state"] == AttemptState.EXECUTING.value
        assert observation["after_child"]["truth"] is None
