from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime

from orket.application.services.gitea_state_control_plane_execution_service import (
    GiteaStateControlPlaneExecutionError,
    GiteaStateControlPlaneExecutionService,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    GiteaStateControlPlaneLeaseService,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
)
from orket.core.contracts import AttemptRecord, FinalTruthRecord, RunRecord, StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SafeContinuationClass,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


CLAIM_FAILURE_CLASS = "gitea_state_claim_failure"


async def close_gitea_state_claim_failure(
    *,
    execution_service: GiteaStateControlPlaneExecutionService | None,
    lease_service: GiteaStateControlPlaneLeaseService | None,
    reservation_service: GiteaStateControlPlaneReservationService | None,
    card_id: str,
    worker_id: str,
    from_state: str,
    error: str,
    lease_observation: Mapping[str, object] | None,
    run_id: str | None,
    attempt_id: str | None,
) -> bool:
    if execution_service is None or run_id is None or attempt_id is None:
        return False
    run = await execution_service.execution_repository.get_run_record(run_id=run_id)
    attempt = await execution_service.execution_repository.get_attempt_record(attempt_id=attempt_id)
    if run is None or attempt is None:
        return False
    existing_truth = await execution_service.publication.repository.get_final_truth(run_id=run_id)
    if existing_truth is not None:
        await _sync_run_truth_id(
            execution_service=execution_service,
            run=run,
            final_truth=existing_truth,
        )
        return True

    step = await _save_failed_claim_step_if_missing(
        execution_service=execution_service,
        run=run,
        attempt=attempt,
        card_id=card_id,
        from_state=from_state,
        error=error,
    )
    if reservation_service is not None and isinstance(lease_observation, Mapping):
        await reservation_service.invalidate_claim_reservation(
            card_id=card_id,
            lease_epoch=GiteaStateControlPlaneExecutionService.lease_epoch_for_run(run_id=run.run_id),
            reason=error,
        )
    if lease_service is not None and isinstance(lease_observation, Mapping):
        await lease_service.publish_uncertain_lease(
            card_id=card_id,
            worker_id=worker_id,
            lease_observation=lease_observation,
            reason=error,
        )
    reconciliation = await execution_service.publication.publish_reconciliation(
        reconciliation_id=_reconciliation_id(run_id=run.run_id),
        target_ref=run.run_id,
        comparison_scope="claim_scope",
        observed_refs=[step.output_ref or step.step_id],
        intended_refs=[
            GiteaStateControlPlaneExecutionService.transition_result_ref(
                card_id=card_id,
                lease_epoch=GiteaStateControlPlaneExecutionService.lease_epoch_for_run(run_id=run.run_id),
                from_state=from_state,
                to_state="in_progress",
            )
        ],
        divergence_class=DivergenceClass.INSUFFICIENT_OBSERVATION,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp=_utc_now(),
        safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
    )

    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.FAILED)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.FAILED_TERMINAL)
    decision = await execution_service.publication.publish_recovery_decision(
        decision_id=f"gitea-state-recovery:{run.run_id}:{CLAIM_FAILURE_CLASS}",
        run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id,
        failure_classification_basis=CLAIM_FAILURE_CLASS,
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="gitea_state_worker_claim_failure_policy.v1",
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref=step.output_ref or step.step_id,
    )
    updated_attempt = attempt.model_copy(
        update={
            "attempt_state": AttemptState.FAILED,
            "end_timestamp": _utc_now(),
            "side_effect_boundary_class": SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
            "failure_class": CLAIM_FAILURE_CLASS,
            "failure_plane": decision.failure_plane,
            "failure_classification": decision.failure_classification,
            "recovery_decision_id": decision.decision_id,
        }
    )
    final_truth = await execution_service.publication.publish_final_truth(
        final_truth_record_id=f"gitea-state-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[AuthoritySourceClass.RECONCILIATION_RECORD, AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref=step.output_ref,
    )
    updated_run = run.model_copy(
        update={
            "lifecycle_state": RunState.FAILED_TERMINAL,
            "final_truth_record_id": final_truth.final_truth_record_id,
        }
    )
    await execution_service.execution_repository.save_attempt_record(record=updated_attempt)
    await execution_service.execution_repository.save_run_record(record=updated_run)
    return True


async def _sync_run_truth_id(
    *,
    execution_service: GiteaStateControlPlaneExecutionService,
    run: RunRecord,
    final_truth: FinalTruthRecord,
) -> None:
    if run.final_truth_record_id == final_truth.final_truth_record_id:
        return
    await execution_service.execution_repository.save_run_record(
        record=run.model_copy(update={"final_truth_record_id": final_truth.final_truth_record_id})
    )


async def _save_failed_claim_step_if_missing(
    *,
    execution_service: GiteaStateControlPlaneExecutionService,
    run: RunRecord,
    attempt: AttemptRecord,
    card_id: str,
    from_state: str,
    error: str,
) -> StepRecord:
    step_id = GiteaStateControlPlaneExecutionService.step_id_for(run_id=run.run_id, stage="claim")
    existing = await execution_service.execution_repository.get_step_record(step_id=step_id)
    if existing is not None:
        return existing
    lease_epoch = GiteaStateControlPlaneExecutionService.lease_epoch_for_run(run_id=run.run_id)
    output_ref = _claim_failure_result_ref(
        card_id=card_id,
        lease_epoch=lease_epoch,
        from_state=from_state,
        error=error,
    )
    return await execution_service.execution_repository.save_step_record(
        record=StepRecord(
            step_id=step_id,
            attempt_id=attempt.attempt_id,
            step_kind="gitea_state_transition",
            namespace_scope=run.namespace_scope,
            input_ref=attempt.starting_state_snapshot_ref,
            output_ref=output_ref,
            capability_used=CapabilityClass.EXTERNAL_MUTATION,
            resources_touched=_resources_touched(card_id=card_id),
            observed_result_classification="state_transition_failed",
            receipt_refs=[attempt.starting_state_snapshot_ref, output_ref],
            closure_classification="step_failed",
        )
    )


def _claim_failure_result_ref(
    *,
    card_id: str,
    lease_epoch: int,
    from_state: str,
    error: str,
) -> str:
    digest = hashlib.sha256(str(error or "claim-failure").encode("utf-8")).hexdigest()
    return (
        f"gitea-card-transition-failure:{str(card_id).strip()}"
        f":lease_epoch:{int(lease_epoch):08d}"
        f":{str(from_state).strip() or 'unknown'}->in_progress"
        f":sha256:{digest}"
    )


def _resources_touched(*, card_id: str) -> list[str]:
    normalized_card_id = str(card_id).strip()
    namespace_scope = GiteaStateControlPlaneExecutionService.namespace_scope_for(card_id=normalized_card_id)
    return [f"gitea-card:{normalized_card_id}", f"issue:{normalized_card_id}", f"namespace:{namespace_scope}"]


def _reconciliation_id(*, run_id: str) -> str:
    return f"gitea-state-reconciliation:{run_id}:claim_failure"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "CLAIM_FAILURE_CLASS",
    "close_gitea_state_claim_failure",
]
