"""Resume reconciliation must commit its complete authority or preserve prior state."""
from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_checkpoint_authority import (
    TurnToolCheckpointRecoveryError,
    resolve_checkpoint_recovery_authority,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import lease_id_for_run
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.services.turn_tool_recovery_transaction import (
    reconcile_orphan_operation_artifacts_atomic,
    recover_pre_effect_attempt_atomic,
)
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import AttemptState, LeaseStatus, ResidualUncertaintyClassification, RunState
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_artifacts import artifact_test_utc_now, write_checkpoint_fixture
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_executor_control_plane import _context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]
INPUTS = dict(session_id="run-1", issue_id="ISSUE-1", role_name="developer", turn_index=1, proposal_hash="proposal")
FAULT = "recovery-write-interrupted"
WRITES = ["save_attempt_record", "save_run_record", "publish_reconciliation",
          "publish_recovery_decision", "publish_final_truth", "publish_lease"]


async def unfinished_turn(tmp_path, *, observed=True):
    control = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control, utc_now=artifact_test_utc_now)
    args = {"path": "agent_output/out.txt", "content": "observed"}
    turn = ExecutionTurn(timestamp=None, role="developer", issue_id="ISSUE-1", content="",
                         tool_calls=[ToolCall(tool="write_file", args=args)])
    await write_checkpoint_fixture(executor=executor, turn=turn, context=_context(), prompt_hash="prompt")
    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    await AsyncFileTools(tmp_path).write_file(args["path"], args["content"])
    if not observed:
        return control, run_id
    await control.publish_step_result(run_id=run_id, attempt_id=f"{run_id}:attempt:0001", step_id="operation-1",
        tool_name="write_file", tool_args=args, result={"ok": True, "touched_paths": [args["path"]]},
        binding=None, operation_id="operation-1", replayed=False)
    return control, run_id


async def resume(control, run_id, evidence):
    if evidence == "effect":
        return await control.begin_execution(**INPUTS, resume_mode=True)
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    checkpoint, acceptance = await resolve_checkpoint_recovery_authority(publication=control.publication, attempt_id=attempt.attempt_id)
    return await reconcile_orphan_operation_artifacts_atomic(
        transactions=control.transactions, publication=control.publication, run=run, current_attempt=attempt,
        checkpoint=checkpoint, acceptance=acceptance, operation_refs=["artifact:agent_output/out.txt"],
    )


def interrupt_write(monkeypatch, method, cancellation):
    owner = AsyncControlPlaneExecutionRepository if method.startswith("save_") else ControlPlanePublicationService
    original = getattr(owner, method)

    async def write(self, **kwargs):
        await original(self, **kwargs)
        if cancellation:
            asyncio.current_task().cancel()
            await asyncio.sleep(0)
        raise RuntimeError(FAULT)

    monkeypatch.setattr(owner, method, write)


@pytest.mark.parametrize("method", WRITES)
@pytest.mark.parametrize("cancellation", [False, True], ids=["exception", "cancel"])
@pytest.mark.parametrize("evidence", ["effect", "orphan"])
# Layer: integration
async def test_interrupted_resume_reconciliation_preserves_complete_prior_authority(tmp_path, monkeypatch, method, cancellation, evidence):
    control, run_id = await unfinished_turn(tmp_path, observed=evidence == "effect")
    before = await logical_state(control.execution_repository.db_path)
    interrupt_write(monkeypatch, method, cancellation)
    task = asyncio.create_task(resume(control, run_id, evidence))
    with pytest.raises(asyncio.CancelledError if cancellation else RuntimeError, match=None if cancellation else FAULT):
        await task
    assert task.done()
    assert await logical_state(control.execution_repository.db_path) == before
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"
    assert len(await control.publication.repository.list_effect_journal_entries(run_id=run_id)) == int(evidence == "effect")


@pytest.mark.parametrize("evidence", ["effect", "orphan"])
# Layer: integration
async def test_reconciled_resume_commits_blocked_truth_before_reporting_refusal(tmp_path, evidence):
    control, run_id = await unfinished_turn(tmp_path, observed=evidence == "effect")
    with pytest.raises(TurnToolCheckpointRecoveryError, match="run was closed from reconciliation evidence"):
        await resume(control, run_id, evidence)
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    truth = await control.publication.repository.get_final_truth(run_id=run_id)
    lease = await control.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    assert run.lifecycle_state is RunState.FAILED_TERMINAL and run.final_truth_record_id == truth.final_truth_record_id
    assert attempt.attempt_state is AttemptState.INTERRUPTED and attempt.end_timestamp is not None
    assert truth.result_class.value == "blocked"
    assert truth.residual_uncertainty_classification is ResidualUncertaintyClassification.UNRESOLVED
    assert lease.status is LeaseStatus.RELEASED
    assert await AsyncFileTools(tmp_path).read_file("agent_output/out.txt") == "observed"


@pytest.mark.parametrize("target", ["run", "attempt"])
# Layer: integration
async def test_stale_recovery_input_cannot_replace_newer_authority(tmp_path, target):
    control, run_id = await unfinished_turn(tmp_path, observed=False)
    run = await control.execution_repository.get_run_record(run_id=run_id)
    attempt = await control.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    if target == "run":
        await control.execution_repository.save_run_record(record=run.model_copy(update={"current_attempt_id": "newer-attempt"}))
    else:
        await control.execution_repository.save_attempt_record(record=attempt.model_copy(update={
            "attempt_state": AttemptState.INTERRUPTED, "end_timestamp": attempt.start_timestamp}))
    before = await logical_state(control.execution_repository.db_path)
    with pytest.raises(TurnToolCheckpointRecoveryError, match="authority changed before transaction admission"):
        await recover_pre_effect_attempt_atomic(transactions=control.transactions,
            publication=control.publication, run=run, current_attempt=attempt)
    assert await logical_state(control.execution_repository.db_path) == before


@pytest.mark.parametrize("cancellation", [False, True], ids=["exception", "cancel"])
# Layer: integration
async def test_pre_effect_resume_decision_rolls_back_after_interrupted_write(tmp_path, monkeypatch, cancellation):
    control, _ = await unfinished_turn(tmp_path, observed=False)
    before = await logical_state(control.execution_repository.db_path)
    interrupt_write(monkeypatch, "publish_recovery_decision", cancellation)
    task = asyncio.create_task(control.begin_execution(**INPUTS, resume_mode=True))
    with pytest.raises(asyncio.CancelledError if cancellation else RuntimeError, match=None if cancellation else FAULT):
        await task
    assert task.done() and await logical_state(control.execution_repository.db_path) == before
