"""Checkpoint recovery cannot turn orphan steps into ordinary execution authority."""
from __future__ import annotations

import aiosqlite
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.turn_tool_checkpoint_authority import TurnToolReconciliationClosed
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.services.turn_tool_recovery_transaction import recover_pre_effect_attempt_atomic
from orket.core.domain import AttemptState, ClosureBasisClassification, ResultClass, RunState
from tests.helpers.step_journal_opening import remove_journal
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_recovery_transaction import INPUTS, unfinished_turn

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("route", ["reentry", "begin"])
# Layer: integration. A retained checkpoint is not an ordinary-execution escape hatch.
async def test_orphan_step_with_checkpoint_refuses_ordinary_execution_unchanged(tmp_path, route):
    control, run_id = await unfinished_turn(tmp_path, orphan_step=True)
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(TurnToolControlPlaneError, match="operation-1.*effect journal"):
        if route == "begin":
            await control.begin_execution(**INPUTS)
        else:
            await control.ensure_reentry_allowed(**{k: v for k, v in INPUTS.items() if k != "proposal_hash"})
    assert await logical_state(control.execution_repository.db_path) == before
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"
    assert await control.publication.repository.list_effect_journal_entries(run_id=run_id) == []


@pytest.mark.parametrize("route", ["reentry", "begin"])
# Layer: integration. Explicit resume still refuses a checkpoint whose acceptance is absent.
async def test_orphan_step_resume_requires_accepted_checkpoint_unchanged(tmp_path, route):
    control, run_id = await unfinished_turn(tmp_path, orphan_step=True)
    checkpoint_id = f"turn-tool-checkpoint:{run_id}:attempt:0001"
    acceptance = await control.publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint_id)
    assert acceptance is not None
    async with aiosqlite.connect(control.execution_repository.db_path) as connection:
        deleted = await connection.execute("DELETE FROM checkpoint_acceptance_records WHERE checkpoint_id = ?", (checkpoint_id,))
        assert deleted.rowcount == 1
        await connection.commit()
    assert await control.publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint_id) is None
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(TurnToolControlPlaneError, match="operation-1.*effect journal"):
        if route == "begin":
            await control.begin_execution(**INPUTS, resume_mode=True)
        else:
            await control.ensure_reentry_allowed(
                **{k: v for k, v in INPUTS.items() if k != "proposal_hash"}, resume_mode=True,
            )
    assert await logical_state(control.execution_repository.db_path) == before
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"


@pytest.mark.parametrize("route", ["reentry", "begin", "atomic"])
# Layer: integration. Unknown dispatch wins over checkpoint-backed orphan reconciliation.
async def test_checkpoint_resume_keeps_unresolved_dispatch_first(tmp_path, route):
    control, run_id = await unfinished_turn(tmp_path)
    await control.prepare_dispatch(run_id=run_id, attempt_id=f"{run_id}:attempt:0001", step_id="unresolved",
        tool_name="write_file", tool_args={"path": "agent_output/other.txt", "content": "unknown"},
        binding=None, operation_id="unresolved")
    await remove_journal(tmp_path / "control_plane.sqlite3", journal_id="turn-tool-journal:operation-1",
        run_id=run_id, attempt_id=f"{run_id}:attempt:0001", step_id="operation-1")
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(ValueError, match="tool dispatch outcome unknown"):
        if route == "begin":
            await control.begin_execution(**INPUTS, resume_mode=True)
        elif route == "reentry":
            await control.ensure_reentry_allowed(
                **{k: v for k, v in INPUTS.items() if k != "proposal_hash"}, resume_mode=True,
            )
        else:
            run = await control.execution_repository.get_run_record(run_id=run_id)
            attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
            await recover_pre_effect_attempt_atomic(transactions=control.transactions, publication=control.publication,
                                                   run=run, current_attempt=attempt)
    assert await logical_state(control.execution_repository.db_path) == before
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"


# Layer: integration. Public resume's transaction closes uncertainty before returning refusal.
async def test_atomic_checkpoint_recovery_closes_orphan_step_without_synthesizing_journal(tmp_path):
    control, run_id = await unfinished_turn(tmp_path, orphan_step=True)
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    with pytest.raises(TurnToolReconciliationClosed, match="run was closed from reconciliation evidence"):
        await recover_pre_effect_attempt_atomic(transactions=control.transactions, publication=control.publication,
                                               run=run, current_attempt=attempt)
    closed = await control.execution_repository.get_run_record(run_id=run_id)
    interrupted = await control.execution_repository.get_attempt_record(attempt_id=attempt.attempt_id)
    truth = await control.publication.repository.get_final_truth(run_id=run_id)
    assert closed.lifecycle_state is RunState.FAILED_TERMINAL
    assert interrupted.attempt_state is AttemptState.INTERRUPTED
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert await control.publication.repository.list_effect_journal_entries(run_id=run_id) == []
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"
