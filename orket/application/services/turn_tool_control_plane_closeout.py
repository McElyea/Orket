from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_support import utc_now
from orket.core.contracts import AttemptRecord, FinalTruthRecord, ReconciliationRecord, RecoveryDecisionRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


def terminal_blocked_actions() -> list[str]:
    return [
        RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE.value,
        RecoveryActionClass.START_NEW_ATTEMPT.value,
        RecoveryActionClass.RESUME_FROM_CHECKPOINT.value,
        RecoveryActionClass.REQUIRE_OBSERVATION_THEN_CONTINUE.value,
        RecoveryActionClass.REQUIRE_RECONCILIATION_THEN_DECIDE.value,
        RecoveryActionClass.PERFORM_CONTROL_PLANE_RECOVERY_ACTION.value,
        RecoveryActionClass.DOWNGRADE_TO_DEGRADED_MODE.value,
    ]


def _dedupe_refs(*refs: str) -> list[str]:
    deduped: list[str] = []
    for ref in refs:
        if ref and ref not in deduped:
            deduped.append(ref)
    return deduped


async def _terminal_recovery_inputs(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    authoritative_result_ref: str,
) -> tuple[str, list[str]]:
    required_refs = [authoritative_result_ref]
    checkpoints = await publication.repository.list_checkpoints(parent_ref=attempt.attempt_id)
    if checkpoints:
        checkpoint = checkpoints[-1]
        required_refs.extend([checkpoint.checkpoint_id, checkpoint.state_snapshot_ref])
        acceptance = await publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
        if acceptance is not None:
            required_refs.append(acceptance.acceptance_id)
    effect_entries = await publication.repository.list_effect_journal_entries(run_id=run.run_id)
    attempt_effects = [entry for entry in effect_entries if entry.attempt_id == attempt.attempt_id]
    rationale_ref = authoritative_result_ref
    if attempt_effects:
        latest_effect = attempt_effects[-1]
        rationale_ref = latest_effect.journal_entry_id
        required_refs.append(latest_effect.journal_entry_id)
        if latest_effect.observed_result_ref is not None:
            required_refs.append(latest_effect.observed_result_ref)
    return rationale_ref, _dedupe_refs(*required_refs)


def ensure_begin_execution_allowed(
    *,
    run: RunRecord,
    current_attempt: AttemptRecord | None,
    error_type: type[Exception],
) -> None:
    if run.lifecycle_state not in {RunState.ADMISSION_PENDING, RunState.ADMITTED, RunState.EXECUTING}:
        raise error_type(
            f"governed turn run {run.run_id} is in {run.lifecycle_state.value}; "
            "explicit recovery or closure is required before execution can continue"
        )
    if current_attempt is None:
        return
    if current_attempt.run_id != run.run_id:
        raise error_type(
            f"governed turn attempt {current_attempt.attempt_id} does not belong to run {run.run_id}"
        )
    if current_attempt.attempt_state not in {AttemptState.CREATED, AttemptState.EXECUTING}:
        raise error_type(
            f"governed turn run {run.run_id} cannot begin ordinary execution from "
            f"{current_attempt.attempt_state.value}; explicit recovery or closure is required"
        )


def ensure_current_execution_target(
    *,
    run: RunRecord,
    attempt: AttemptRecord,
    operation_name: str,
    error_type: type[Exception],
) -> None:
    if attempt.run_id != run.run_id:
        raise error_type(
            f"{operation_name} attempt {attempt.attempt_id} does not belong to governed run {run.run_id}"
        )
    if run.current_attempt_id != attempt.attempt_id:
        raise error_type(
            f"{operation_name} requires the current governed attempt; "
            f"run {run.run_id} points to {run.current_attempt_id or 'none'} not {attempt.attempt_id}"
        )
    if run.lifecycle_state is not RunState.EXECUTING:
        raise error_type(
            f"{operation_name} requires an executing governed run; found {run.lifecycle_state.value}"
        )
    if attempt.attempt_state is not AttemptState.EXECUTING:
        raise error_type(
            f"{operation_name} requires an executing governed attempt; found {attempt.attempt_state.value}"
        )


async def finalize_turn_execution(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    authoritative_result_ref: str,
    violation_reasons: list[str],
    executed_step_count: int,
    error_type: type[Exception],
) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord]:
    existing_truth = await publication.repository.get_final_truth(run_id=run.run_id)
    if existing_truth is not None:
        if run.final_truth_record_id != existing_truth.final_truth_record_id:
            run = run.model_copy(update={"final_truth_record_id": existing_truth.final_truth_record_id})
            await execution_repository.save_run_record(record=run)
        return run, attempt, existing_truth

    ensure_current_execution_target(
        run=run,
        attempt=attempt,
        operation_name="finalize_execution",
        error_type=error_type,
    )
    closed_at = utc_now()
    if not violation_reasons:
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.COMPLETED)
        attempt = attempt.model_copy(update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": closed_at})
        await execution_repository.save_attempt_record(record=attempt)
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.COMPLETED)
        truth = await publication.publish_final_truth(
            final_truth_record_id=f"turn-tool-final-truth:{run.run_id}",
            run_id=run.run_id,
            result_class=ResultClass.SUCCESS,
            completion_classification=CompletionClassification.SATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
            authority_sources=[
                AuthoritySourceClass.RECEIPT_EVIDENCE,
                AuthoritySourceClass.VALIDATED_ARTIFACT,
            ],
            authoritative_result_ref=authoritative_result_ref,
        )
        run = run.model_copy(
            update={"lifecycle_state": RunState.COMPLETED, "final_truth_record_id": truth.final_truth_record_id}
        )
        await execution_repository.save_run_record(record=run)
        return run, attempt, truth

    pre_effect_failure = executed_step_count == 0
    failure_class = "tool_execution_blocked" if pre_effect_failure else "tool_execution_failed"
    boundary = (
        SideEffectBoundaryClass.PRE_EFFECT_FAILURE
        if pre_effect_failure
        else SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    )
    rationale_ref, required_precondition_refs = await _terminal_recovery_inputs(
        publication=publication,
        run=run,
        attempt=attempt,
        authoritative_result_ref=authoritative_result_ref,
    )
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.FAILED)
    decision = await publication.publish_recovery_decision(
        decision_id=f"turn-tool-recovery:{run.run_id}:{failure_class}",
        run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id,
        failure_classification_basis=failure_class,
        side_effect_boundary_class=boundary,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref=rationale_ref,
        required_precondition_refs=required_precondition_refs,
        blocked_actions=terminal_blocked_actions(),
    )
    attempt = attempt.model_copy(
        update={
            "attempt_state": AttemptState.FAILED,
            "end_timestamp": closed_at,
            "side_effect_boundary_class": boundary,
            "failure_class": failure_class,
            "recovery_decision_id": decision.decision_id,
        }
    )
    await execution_repository.save_attempt_record(record=attempt)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.FAILED_TERMINAL)
    truth = await publication.publish_final_truth(
        final_truth_record_id=f"turn-tool-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=ResultClass.BLOCKED if pre_effect_failure else ResultClass.FAILED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=(
            ClosureBasisClassification.POLICY_TERMINAL_STOP
            if pre_effect_failure
            else ClosureBasisClassification.NORMAL_EXECUTION
        ),
        authority_sources=(
            [AuthoritySourceClass.RECEIPT_EVIDENCE]
            if pre_effect_failure
            else [AuthoritySourceClass.RECEIPT_EVIDENCE, AuthoritySourceClass.VALIDATED_ARTIFACT]
        ),
        authoritative_result_ref=authoritative_result_ref,
    )
    run = run.model_copy(
        update={"lifecycle_state": RunState.FAILED_TERMINAL, "final_truth_record_id": truth.final_truth_record_id}
    )
    await execution_repository.save_run_record(record=run)
    return run, attempt, truth


async def close_reconciliation_required_resume_mode(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    reconciliation: ReconciliationRecord,
    side_effect_boundary_class: SideEffectBoundaryClass,
    failure_classification_basis: str,
    required_precondition_refs: list[str],
) -> tuple[RunRecord, AttemptRecord, RecoveryDecisionRecord, FinalTruthRecord]:
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.FAILED_TERMINAL)
    decision = await publication.publish_recovery_decision(
        decision_id=f"turn-tool-recovery:{run.run_id}:reconciliation-close:{attempt.attempt_ordinal:04d}",
        run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id,
        failure_classification_basis=failure_classification_basis,
        side_effect_boundary_class=side_effect_boundary_class,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref=reconciliation.reconciliation_id,
        required_precondition_refs=_dedupe_refs(
            reconciliation.reconciliation_id,
            *required_precondition_refs,
        ),
        blocked_actions=terminal_blocked_actions(),
        reconciliation_record=reconciliation,
    )
    updated_attempt = attempt.model_copy(update={"recovery_decision_id": decision.decision_id})
    await execution_repository.save_attempt_record(record=updated_attempt)
    truth = await publication.publish_final_truth(
        final_truth_record_id=f"turn-tool-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[AuthoritySourceClass.RECONCILIATION_RECORD],
        authoritative_result_ref=reconciliation.reconciliation_id,
    )
    updated_run = run.model_copy(
        update={"lifecycle_state": RunState.FAILED_TERMINAL, "final_truth_record_id": truth.final_truth_record_id}
    )
    await execution_repository.save_run_record(record=updated_run)
    return updated_run, updated_attempt, decision, truth


__all__ = [
    "close_reconciliation_required_resume_mode",
    "ensure_begin_execution_allowed",
    "ensure_current_execution_target",
    "finalize_turn_execution",
    "terminal_blocked_actions",
]
