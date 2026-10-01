"""Metadata lineage must bind one run and source attempt without repairing history."""
from __future__ import annotations

import pytest

from orket.application.services.turn_tool_checkpoint_authority import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_recovery import load_checkpoint_resume_lineage
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_checkpoint_resume_lineage_retention import MODES, admitted_lineage, overwrite_record
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("mode", MODES, ids=["same-attempt", "replacement-attempt"])
@pytest.mark.parametrize("damage", ["unchanged", "failed-parent", "decision-run", "checkpoint-parent"])
# Layer: integration
async def test_checkpoint_resume_binds_retained_run_and_failed_parent(tmp_path, mode, damage):
    db, control, run, _, resumed, decision, checkpoint, acceptance = await admitted_lineage(tmp_path, mode)
    foreign_run, foreign = await control.begin_execution(session_id="foreign-session", issue_id="ISSUE-2",
        role_name="developer", turn_index=1, proposal_hash="foreign-proposal")
    if damage in {"failed-parent", "decision-run"}:
        change = {"failed_attempt_id": foreign.attempt_id} if damage == "failed-parent" else {"run_id": foreign_run.run_id}
        changed = type(decision).model_validate({**decision.model_dump(), **change})
        await overwrite_record(db, "recovery_decision_records", "decision_id", decision.decision_id, changed)
    elif damage == "checkpoint-parent":
        changed = type(checkpoint).model_validate({**checkpoint.model_dump(), "parent_ref": foreign.attempt_id})
        await overwrite_record(db, "checkpoint_records", "checkpoint_id", checkpoint.checkpoint_id, changed)
    before = await logical_state(db)
    arguments = dict(execution_repository=control.execution_repository, publication=control.publication,
                     run_id=run.run_id, resumed_attempt=resumed)
    if damage == "unchanged":
        assert await load_checkpoint_resume_lineage(**arguments) == (decision, checkpoint, acceptance)
    else:
        with pytest.raises(TurnToolCheckpointRecoveryError):
            await load_checkpoint_resume_lineage(**arguments)
    assert await logical_state(db) == before
    assert await control.publication.repository.get_final_truth(run_id=run.run_id) is None
    assert await control.publication.repository.list_effect_journal_entries(run_id=run.run_id) == []
    assert await control.execution_repository.list_step_records(attempt_id=resumed.attempt_id) == []
