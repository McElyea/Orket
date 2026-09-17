"""One transaction for turn recovery; committed refusal is distinct from failure."""
from __future__ import annotations

from contextlib import asynccontextmanager

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_checkpoint_authority import (
    TurnToolCheckpointRecoveryError,
    TurnToolReconciliationClosed,
)
from orket.application.services.turn_tool_control_plane_closeout import ensure_current_execution_target
from orket.application.services.turn_tool_control_plane_recovery import (
    fail_closed_on_orphan_operation_artifacts_for_resume_mode,
    recover_pre_effect_attempt_for_resume_mode,
)
from orket.application.services.turn_tool_control_plane_state_gate import (
    require_resolved_tool_dispatches,
    require_turn_dispatch_contract,
)
from orket.core.contracts import AttemptRecord, CheckpointAcceptanceRecord, CheckpointRecord, RunRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory


@asynccontextmanager
async def turn_tool_transaction(transactions: ControlPlaneTransactionFactory):
    """Commit completed reconciliation refusal; roll back every other interruption."""
    closed = None
    async with transactions() as transaction:
        try:
            yield transaction
        except TurnToolReconciliationClosed as exc:
            closed = exc
    if closed is not None:
        raise closed


@asynccontextmanager
async def _recovery_transaction(*, transactions, publication, run, current_attempt):
    expected_run = RunRecord.model_validate_json(run.model_dump_json())
    expected_attempt = AttemptRecord.model_validate_json(current_attempt.model_dump_json())
    async with turn_tool_transaction(transactions) as transaction:
        retained_run = await transaction.execution.get_run_record(run_id=expected_run.run_id)
        retained_attempt = await transaction.execution.get_attempt_record(attempt_id=expected_attempt.attempt_id)
        if retained_run != expected_run or retained_attempt != expected_attempt:
            raise TurnToolCheckpointRecoveryError("turn recovery authority changed before transaction admission")
        await require_turn_dispatch_contract(transaction.records, retained_run, TurnToolCheckpointRecoveryError)
        ensure_current_execution_target(run=retained_run, attempt=retained_attempt,
            operation_name="turn recovery", error_type=TurnToolCheckpointRecoveryError)
        await require_resolved_tool_dispatches(transaction.execution, retained_run, TurnToolCheckpointRecoveryError)
        scoped = ControlPlanePublicationService(repository=transaction.records, authority=publication.authority)
        yield transaction.execution, scoped, retained_run, retained_attempt


async def recover_pre_effect_attempt_atomic(
    *, transactions: ControlPlaneTransactionFactory, publication: ControlPlanePublicationService,
    run: RunRecord, current_attempt: AttemptRecord,
) -> tuple[RunRecord, AttemptRecord]:
    async with _recovery_transaction(transactions=transactions, publication=publication,
                                     run=run, current_attempt=current_attempt) as (execution, scoped, retained_run, retained_attempt):
        return await recover_pre_effect_attempt_for_resume_mode(execution_repository=execution, publication=scoped,
                                               run=retained_run, current_attempt=retained_attempt)


async def reconcile_orphan_operation_artifacts_atomic(
    *, transactions: ControlPlaneTransactionFactory, publication: ControlPlanePublicationService,
    run: RunRecord, current_attempt: AttemptRecord, checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord, operation_refs: list[str],
) -> None:
    if not operation_refs:
        return
    expected_checkpoint = CheckpointRecord.model_validate_json(checkpoint.model_dump_json())
    expected_acceptance = CheckpointAcceptanceRecord.model_validate_json(acceptance.model_dump_json())
    observed_refs = list(operation_refs)
    async with _recovery_transaction(transactions=transactions, publication=publication,
                                     run=run, current_attempt=current_attempt) as (execution, scoped, retained_run, retained_attempt):
        stored_checkpoint = await scoped.repository.get_checkpoint(checkpoint_id=expected_checkpoint.checkpoint_id)
        stored_acceptance = await scoped.repository.get_checkpoint_acceptance(checkpoint_id=expected_checkpoint.checkpoint_id)
        if stored_checkpoint != expected_checkpoint or stored_acceptance != expected_acceptance:
            raise TurnToolCheckpointRecoveryError("turn recovery checkpoint authority changed before transaction admission")
        await fail_closed_on_orphan_operation_artifacts_for_resume_mode(execution_repository=execution, publication=scoped,
            run=retained_run, current_attempt=retained_attempt, checkpoint=stored_checkpoint,
            acceptance=stored_acceptance, operation_refs=observed_refs)
