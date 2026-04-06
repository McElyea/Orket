from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_closeout import close_reconciliation_required_resume_mode
from orket.application.services.turn_tool_control_plane_reconciliation import publish_resume_reconciliation
from orket.application.services.turn_tool_control_plane_support import attempt_id_for, utc_now
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
    RunRecord,
    StepRecord,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    RecoveryActionClass,
    RunState,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


class TurnToolCheckpointRecoveryError(ValueError):
    """Raised when governed turn checkpoint recovery would exceed authority."""


def _same_attempt_resume_decision_id(*, run_id: str, attempt_ordinal: int) -> str:
    return f"turn-tool-recovery:{run_id}:same-attempt:{int(attempt_ordinal):04d}"


async def recover_pre_effect_attempt_for_resume_mode(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    current_attempt: AttemptRecord,
) -> tuple[RunRecord, AttemptRecord]:
    step_records = await execution_repository.list_step_records(attempt_id=current_attempt.attempt_id)
    effect_entries = await publication.repository.list_effect_journal_entries(run_id=run.run_id)
    attempt_effect_entries = [entry for entry in effect_entries if entry.attempt_id == current_attempt.attempt_id]
    if current_attempt.attempt_ordinal > 1 and current_attempt.attempt_state is AttemptState.EXECUTING:
        if step_records or attempt_effect_entries:
            _, checkpoint, acceptance = await load_checkpoint_resume_lineage(
                execution_repository=execution_repository,
                publication=publication,
                run_id=run.run_id,
                resumed_attempt=current_attempt,
            )
            await _escalate_reconciliation_required_resume_mode(
                execution_repository=execution_repository,
                publication=publication,
                run=run,
                current_attempt=current_attempt,
                checkpoint=checkpoint,
                acceptance=acceptance,
                step_records=step_records,
                effect_entries=attempt_effect_entries,
                operation_refs=[],
            )
        return run, current_attempt
    checkpoint, checkpoint_acceptance = await _resolve_checkpoint_recovery_authority(
        publication=publication,
        attempt_id=current_attempt.attempt_id,
    )
    resumability_class, accepted_checkpoint = _validate_checkpoint_recovery_inputs(
        run=run,
        current_attempt=current_attempt,
        checkpoint=checkpoint,
        acceptance=checkpoint_acceptance,
    )
    if step_records or attempt_effect_entries:
        await _escalate_reconciliation_required_resume_mode(
            execution_repository=execution_repository,
            publication=publication,
            run=run,
            current_attempt=current_attempt,
            checkpoint=checkpoint,
            acceptance=acceptance,
            step_records=step_records,
            effect_entries=attempt_effect_entries,
            operation_refs=[],
        )
    if resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT:
        await publication.publish_recovery_decision(
            decision_id=_same_attempt_resume_decision_id(
                run_id=run.run_id,
                attempt_ordinal=current_attempt.attempt_ordinal,
            ),
            run_id=run.run_id,
            failed_attempt_id=current_attempt.attempt_id,
            failure_classification_basis="unfinished_pre_effect_attempt",
            side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
            recovery_policy_ref=run.policy_snapshot_id,
            authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
            rationale_ref=accepted_checkpoint.acceptance_id,
            resumed_attempt_id=current_attempt.attempt_id,
            target_checkpoint_id=checkpoint.checkpoint_id,
            required_precondition_refs=[
                checkpoint.checkpoint_id,
                accepted_checkpoint.acceptance_id,
                checkpoint.state_snapshot_ref,
            ],
            checkpoint_acceptance=accepted_checkpoint,
        )
        return run, current_attempt

    interrupted_at = utc_now()
    validate_attempt_state_transition(current_state=current_attempt.attempt_state, next_state=AttemptState.INTERRUPTED)
    interrupted_attempt = current_attempt.model_copy(
        update={
            "attempt_state": AttemptState.INTERRUPTED,
            "end_timestamp": interrupted_at,
            "side_effect_boundary_class": SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
            "failure_class": "unfinished_pre_effect_attempt",
        }
    )
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.RECOVERY_PENDING)
    recovery_pending_run = run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
    await execution_repository.save_attempt_record(record=interrupted_attempt)
    await execution_repository.save_run_record(record=recovery_pending_run)

    next_attempt_ordinal = max(current_attempt.attempt_ordinal, 1) + 1
    next_attempt_id = attempt_id_for(run_id=run.run_id, ordinal=next_attempt_ordinal)
    decision = await publication.publish_recovery_decision(
        decision_id=f"turn-tool-recovery:{run.run_id}:{next_attempt_ordinal:04d}",
        run_id=run.run_id,
        failed_attempt_id=current_attempt.attempt_id,
        failure_classification_basis="unfinished_pre_effect_attempt",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        rationale_ref=accepted_checkpoint.acceptance_id,
        new_attempt_id=next_attempt_id,
        target_checkpoint_id=checkpoint.checkpoint_id,
        required_precondition_refs=[
            checkpoint.checkpoint_id,
            accepted_checkpoint.acceptance_id,
            checkpoint.state_snapshot_ref,
        ],
        checkpoint_acceptance=accepted_checkpoint,
    )
    interrupted_attempt = interrupted_attempt.model_copy(update={"recovery_decision_id": decision.decision_id, "failure_plane": decision.failure_plane, "failure_classification": decision.failure_classification})
    await execution_repository.save_attempt_record(record=interrupted_attempt)

    validate_run_state_transition(current_state=recovery_pending_run.lifecycle_state, next_state=RunState.RECOVERING)
    recovering_run = recovery_pending_run.model_copy(update={"lifecycle_state": RunState.RECOVERING})
    await execution_repository.save_run_record(record=recovering_run)

    resumed_attempt = AttemptRecord(
        attempt_id=next_attempt_id,
        run_id=run.run_id,
        attempt_ordinal=next_attempt_ordinal,
        attempt_state=AttemptState.EXECUTING,
        starting_state_snapshot_ref=checkpoint.state_snapshot_ref,
        start_timestamp=interrupted_at,
    )
    await execution_repository.save_attempt_record(record=resumed_attempt)

    validate_run_state_transition(current_state=recovering_run.lifecycle_state, next_state=RunState.EXECUTING)
    resumed_run = recovering_run.model_copy(
        update={
            "lifecycle_state": RunState.EXECUTING,
            "current_attempt_id": resumed_attempt.attempt_id,
        }
    )
    await execution_repository.save_run_record(record=resumed_run)
    return resumed_run, resumed_attempt


async def fail_closed_on_orphan_operation_artifacts_for_resume_mode(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    current_attempt: AttemptRecord,
    checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord,
    operation_refs: list[str],
) -> None:
    if not operation_refs:
        return
    _validate_checkpoint_recovery_inputs(
        run=run,
        current_attempt=current_attempt,
        checkpoint=checkpoint,
        acceptance=acceptance,
    )
    await _escalate_reconciliation_required_resume_mode(
        execution_repository=execution_repository,
        publication=publication,
        run=run,
        current_attempt=current_attempt,
        checkpoint=checkpoint,
        acceptance=acceptance,
        step_records=[],
        effect_entries=[],
        operation_refs=operation_refs,
    )


async def _resolve_checkpoint_recovery_authority(
    *,
    publication: ControlPlanePublicationService,
    attempt_id: str,
) -> tuple[CheckpointRecord, CheckpointAcceptanceRecord | None]:
    checkpoints = await publication.repository.list_checkpoints(parent_ref=attempt_id)
    if not checkpoints:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an accepted governed turn checkpoint for attempt {attempt_id}"
        )
    checkpoint = checkpoints[-1]
    acceptance = await publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
    return checkpoint, acceptance


async def load_checkpoint_resume_lineage(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run_id: str,
    resumed_attempt: AttemptRecord,
) -> tuple[RecoveryDecisionRecord, CheckpointRecord, CheckpointAcceptanceRecord]:
    if resumed_attempt.attempt_ordinal < 1:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode did not create or resolve a governed attempt for {run_id}"
        )
    if resumed_attempt.attempt_ordinal == 1:
        checkpoint, checkpoint_acceptance = await _resolve_checkpoint_recovery_authority(
            publication=publication,
            attempt_id=resumed_attempt.attempt_id,
        )
        if checkpoint_acceptance is None or checkpoint_acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} is missing accepted checkpoint lineage"
            )
        if checkpoint.resumability_class is not CheckpointResumabilityClass.RESUME_SAME_ATTEMPT:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} requires same-attempt checkpoint lineage"
            )
        if checkpoint_acceptance.resumability_class is not CheckpointResumabilityClass.RESUME_SAME_ATTEMPT:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} is missing accepted same-attempt checkpoint lineage"
            )
        if checkpoint.parent_ref != resumed_attempt.attempt_id:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} does not match checkpoint parent lineage"
            )
        decision_id = _same_attempt_resume_decision_id(
            run_id=run_id,
            attempt_ordinal=resumed_attempt.attempt_ordinal,
        )
        recovery_decision = await publication.repository.get_recovery_decision(decision_id=decision_id)
        if recovery_decision is None:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} is missing durable same-attempt recovery decision lineage"
            )
        if recovery_decision.authorized_next_action is not RecoveryActionClass.RESUME_FROM_CHECKPOINT:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} does not carry checkpoint-resume lineage"
            )
        if recovery_decision.resumed_attempt_id != resumed_attempt.attempt_id or recovery_decision.new_attempt_id is not None:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} does not align with same-attempt recovery lineage"
            )
        if recovery_decision.target_checkpoint_id != checkpoint.checkpoint_id:
            raise TurnToolCheckpointRecoveryError(
                f"resumed governed attempt {resumed_attempt.attempt_id} does not align with checkpoint lineage"
            )
        return recovery_decision, checkpoint, checkpoint_acceptance
    if resumed_attempt.attempt_ordinal < 2:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode did not create or resolve a replacement governed attempt for {run_id}"
        )
    attempts = await execution_repository.list_attempt_records(run_id=run_id)
    prior_attempt = next(
        (candidate for candidate in attempts if candidate.attempt_ordinal == resumed_attempt.attempt_ordinal - 1),
        None,
    )
    if prior_attempt is None or prior_attempt.recovery_decision_id is None:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} is missing recovery lineage"
        )
    recovery_decision = await publication.repository.get_recovery_decision(decision_id=prior_attempt.recovery_decision_id)
    if recovery_decision is None:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} is missing durable recovery decision lineage"
        )
    if recovery_decision.authorized_next_action is not RecoveryActionClass.RESUME_FROM_CHECKPOINT:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} does not carry checkpoint-resume lineage"
        )
    if recovery_decision.new_attempt_id != resumed_attempt.attempt_id or recovery_decision.target_checkpoint_id is None:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} does not align with recovery decision lineage"
        )
    recovery_checkpoint = await publication.repository.get_checkpoint(checkpoint_id=recovery_decision.target_checkpoint_id)
    if recovery_checkpoint is None:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} is missing checkpoint lineage"
        )
    checkpoint_acceptance = await publication.repository.get_checkpoint_acceptance(
        checkpoint_id=recovery_checkpoint.checkpoint_id
    )
    if checkpoint_acceptance is None or checkpoint_acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} is missing accepted checkpoint lineage"
        )
    if recovery_checkpoint.resumability_class is not CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} requires new-attempt checkpoint lineage"
        )
    if checkpoint_acceptance.resumability_class is not CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} is missing accepted new-attempt checkpoint lineage"
        )
    if recovery_checkpoint.state_snapshot_ref != resumed_attempt.starting_state_snapshot_ref:
        raise TurnToolCheckpointRecoveryError(
            f"resumed governed attempt {resumed_attempt.attempt_id} does not match checkpoint snapshot lineage"
        )
    return recovery_decision, recovery_checkpoint, checkpoint_acceptance


async def _escalate_reconciliation_required_resume_mode(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    current_attempt: AttemptRecord,
    checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord,
    step_records: list[StepRecord],
    effect_entries: list[EffectJournalEntryRecord],
    operation_refs: list[str],
) -> None:
    interrupted_at = utc_now()
    boundary = (
        SideEffectBoundaryClass.POST_EFFECT_OBSERVED
        if effect_entries
        else SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
    )
    failure_basis = (
        "unfinished_post_effect_attempt"
        if effect_entries
        else "unfinished_effect_boundary_uncertain_attempt"
    )
    rationale_ref = (
        effect_entries[-1].journal_entry_id
        if effect_entries
        else (step_records[-1].step_id if step_records else operation_refs[-1])
    )
    validate_attempt_state_transition(current_state=current_attempt.attempt_state, next_state=AttemptState.INTERRUPTED)
    interrupted_attempt = current_attempt.model_copy(
        update={
            "attempt_state": AttemptState.INTERRUPTED,
            "end_timestamp": interrupted_at,
            "side_effect_boundary_class": boundary,
            "failure_class": failure_basis,
        }
    )
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.RECOVERY_PENDING)
    recovery_pending_run = run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
    await execution_repository.save_attempt_record(record=interrupted_attempt)
    await execution_repository.save_run_record(record=recovery_pending_run)
    reconciliation, required_scope_refs = await publish_resume_reconciliation(
        publication=publication,
        run=recovery_pending_run,
        checkpoint=checkpoint,
        acceptance=acceptance,
        step_refs=[step.step_id for step in step_records],
        effect_refs=[entry.journal_entry_id for entry in effect_entries],
        operation_refs=operation_refs,
    )
    validate_run_state_transition(current_state=recovery_pending_run.lifecycle_state, next_state=RunState.RECONCILING)
    reconciling_run = recovery_pending_run.model_copy(update={"lifecycle_state": RunState.RECONCILING})
    await execution_repository.save_run_record(record=reconciling_run)
    decision = await publication.publish_recovery_decision(
        decision_id=f"turn-tool-recovery:{run.run_id}:reconcile:{current_attempt.attempt_ordinal:04d}",
        run_id=run.run_id,
        failed_attempt_id=current_attempt.attempt_id,
        failure_classification_basis=failure_basis,
        side_effect_boundary_class=boundary,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.REQUIRE_RECONCILIATION_THEN_DECIDE,
        rationale_ref=reconciliation.reconciliation_id,
        required_precondition_refs=[
            *required_scope_refs,
            rationale_ref,
        ],
        reconciliation_record=reconciliation,
    )
    interrupted_attempt = interrupted_attempt.model_copy(update={"recovery_decision_id": decision.decision_id, "failure_plane": decision.failure_plane, "failure_classification": decision.failure_classification})
    await execution_repository.save_attempt_record(record=interrupted_attempt)
    terminal_failure_basis = (
        "reconciliation_closed_unexpected_effect_observed"
        if effect_entries
        else "reconciliation_closed_insufficient_observation"
    )
    await close_reconciliation_required_resume_mode(
        execution_repository=execution_repository,
        publication=publication,
        run=reconciling_run,
        attempt=interrupted_attempt,
        reconciliation=reconciliation,
        side_effect_boundary_class=boundary,
        failure_classification_basis=terminal_failure_basis,
        required_precondition_refs=[
            *required_scope_refs,
            rationale_ref,
        ],
    )
    if effect_entries:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode encountered governed turn effect truth beyond the pre-effect checkpoint; "
            "continuation remains unavailable and the run was closed from reconciliation evidence"
        )
    if operation_refs:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode encountered durable operation artifacts without matching control-plane step/effect truth; "
            "continuation remains unavailable and the run was closed from reconciliation evidence"
        )
    raise TurnToolCheckpointRecoveryError(
        "resume_mode encountered governed turn step truth without matching effect authority; "
        "continuation remains unavailable and the run was closed from reconciliation evidence"
    )


def _validate_checkpoint_recovery_inputs(
    *,
    run: RunRecord,
    current_attempt: AttemptRecord,
    checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord | None,
) -> tuple[CheckpointResumabilityClass, CheckpointAcceptanceRecord]:
    if run.lifecycle_state is not RunState.EXECUTING:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an unfinished executing run; found {run.lifecycle_state.value}"
        )
    if current_attempt.attempt_state is not AttemptState.EXECUTING:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires an unfinished executing attempt; found {current_attempt.attempt_state.value}"
        )
    if acceptance is None or acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
        raise TurnToolCheckpointRecoveryError(
            f"resume_mode requires accepted checkpoint authority for {checkpoint.checkpoint_id}"
        )
    if checkpoint.resumability_class not in {
        CheckpointResumabilityClass.RESUME_SAME_ATTEMPT,
        CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
    }:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode requires a resumable governed turn checkpoint"
        )
    if acceptance.resumability_class is not checkpoint.resumability_class:
        raise TurnToolCheckpointRecoveryError(
            "resume_mode requires checkpoint acceptance that matches checkpoint resumability"
        )
    return checkpoint.resumability_class, acceptance


__all__ = [
    "TurnToolCheckpointRecoveryError",
    "fail_closed_on_orphan_operation_artifacts_for_resume_mode",
    "load_checkpoint_resume_lineage",
    "recover_pre_effect_attempt_for_resume_mode",
]
