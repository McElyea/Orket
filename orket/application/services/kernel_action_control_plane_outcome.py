from __future__ import annotations

from typing import Any

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_failure import failure_projection_for_commit_status
from orket.application.services.kernel_action_control_plane_support import (
    authority_sources_for_commit,
    final_truth_projection_for_commit,
    has_validation_evidence,
    optional_text,
    required_text,
)
from orket.core.contracts import AttemptRecord, FinalTruthRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    DegradationClassification,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
)


class KernelActionControlPlaneOutcomeError(ValueError):
    """Raised when governed action commit outcome publication cannot be represented honestly."""


async def enter_attempt_execution_if_needed(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    attempt: AttemptRecord,
    run_id: str,
    execution_timestamp: str,
    allow_claim_only: bool,
    observed_execution: bool,
) -> AttemptRecord:
    if attempt.attempt_state is AttemptState.EXECUTING:
        return attempt
    if attempt.attempt_state is not AttemptState.CREATED:
        raise KernelActionControlPlaneOutcomeError(f"unexpected attempt state for governed action {run_id}")
    if not allow_claim_only and not observed_execution:
        return attempt
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
    updated = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING, "start_timestamp": execution_timestamp})
    await execution_repository.save_attempt_record(record=updated)
    return updated


async def finalize_attempt_from_commit(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    attempt: AttemptRecord,
    run_id: str,
    status: str,
    committed_at: str,
    observed_execution: bool,
) -> AttemptRecord:
    if status == "COMMITTED":
        if attempt.attempt_state is AttemptState.CREATED:
            attempt = await enter_attempt_execution_if_needed(
                execution_repository=execution_repository,
                attempt=attempt,
                run_id=run_id,
                execution_timestamp=committed_at,
                allow_claim_only=True,
                observed_execution=observed_execution,
            )
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.COMPLETED)
        updated = attempt.model_copy(update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": committed_at})
        await execution_repository.save_attempt_record(record=updated)
        return updated
    if observed_execution:
        if attempt.attempt_state is AttemptState.CREATED:
            attempt = await enter_attempt_execution_if_needed(
                execution_repository=execution_repository,
                attempt=attempt,
                run_id=run_id,
                execution_timestamp=committed_at,
                allow_claim_only=False,
                observed_execution=True,
            )
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.FAILED)
        failure_basis, failure_plane, failure_classification = failure_projection_for_commit_status(status=status)
        updated = attempt.model_copy(
            update={
                "attempt_state": AttemptState.FAILED,
                "end_timestamp": committed_at,
                "side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                "failure_class": failure_basis,
                "failure_plane": failure_plane,
                "failure_classification": failure_classification,
            }
        )
        await execution_repository.save_attempt_record(record=updated)
        return updated
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.ABANDONED)
    updated = attempt.model_copy(update={"attempt_state": AttemptState.ABANDONED, "end_timestamp": committed_at})
    await execution_repository.save_attempt_record(record=updated)
    return updated


async def publish_final_truth_for_commit(
    *,
    publication: ControlPlanePublicationService,
    run_id: str,
    request: dict[str, Any],
    response: dict[str, Any],
    status: str,
    observed_execution: bool,
) -> FinalTruthRecord:
    existing = await publication.repository.get_final_truth(run_id=run_id)
    if existing is not None:
        return existing
    result_class, completion, evidence, residual, closure = final_truth_projection_for_commit(
        status=status,
        observed_execution=observed_execution,
        validated=has_validation_evidence(request=request, response=response, ledger_items=()),
        claimed_result=bool(optional_text(request, "execution_result_digest")),
    )
    authoritative_result_ref = optional_text(request, "execution_result_digest")
    if authoritative_result_ref:
        authoritative_result_ref = f"kernel-execution-result:{authoritative_result_ref}"
    else:
        authoritative_result_ref = required_text(response, "commit_event_digest")
    return await publication.publish_final_truth(
        final_truth_record_id=f"kernel-action-final-truth:{run_id}",
        run_id=run_id,
        result_class=result_class,
        completion_classification=completion,
        evidence_sufficiency_classification=evidence,
        residual_uncertainty_classification=residual,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=closure,
        authority_sources=authority_sources_for_commit(evidence=evidence),
        authoritative_result_ref=authoritative_result_ref,
    )


__all__ = [
    "KernelActionControlPlaneOutcomeError",
    "enter_attempt_execution_if_needed",
    "finalize_attempt_from_commit",
    "publish_final_truth_for_commit",
]
