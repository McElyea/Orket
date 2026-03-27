from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    ControlPlaneFailureClass,
    ExecutionFailureClass,
    FailurePlane,
    RecoveryActionClass,
    SideEffectBoundaryClass,
    TruthFailureClass,
)


def failure_projection_for_commit_status(
    *,
    status: str,
) -> tuple[str, FailurePlane, ExecutionFailureClass | TruthFailureClass | ControlPlaneFailureClass]:
    normalized = str(status or "").strip().upper()
    if normalized == "REJECTED_POLICY":
        return "kernel_action_policy_rejected", FailurePlane.TRUTH, TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    if normalized == "ERROR":
        return "kernel_action_error", FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE
    return (
        "kernel_action_commit_failed",
        FailurePlane.CONTROL_PLANE,
        ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
    )


async def publish_failed_commit_recovery_decision(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    status: str,
    rationale_ref: str,
) -> AttemptRecord:
    if attempt.recovery_decision_id is not None:
        return attempt
    failure_basis, failure_plane, failure_classification = failure_projection_for_commit_status(status=status)
    decision = await publication.publish_recovery_decision(
        decision_id=f"kernel-action-recovery:{run.run_id}:{status.lower()}",
        run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id,
        failure_classification_basis=failure_basis,
        failure_plane=failure_plane,
        failure_classification=failure_classification,
        side_effect_boundary_class=SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref=rationale_ref,
    )
    updated = attempt.model_copy(
        update={
            "recovery_decision_id": decision.decision_id,
            "failure_plane": decision.failure_plane,
            "failure_classification": decision.failure_classification,
        }
    )
    await execution_repository.save_attempt_record(record=updated)
    return updated


async def publish_pre_effect_terminal_commit_recovery_decision(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    status: str,
    rationale_ref: str,
) -> AttemptRecord:
    if attempt.recovery_decision_id is not None:
        return attempt
    failure_basis, failure_plane, failure_classification = failure_projection_for_commit_status(status=status)
    decision = await publication.publish_recovery_decision(
        decision_id=f"kernel-action-recovery:{run.run_id}:{status.lower()}:pre_effect",
        run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id,
        failure_classification_basis=failure_basis,
        failure_plane=failure_plane,
        failure_classification=failure_classification,
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref=run.policy_snapshot_id,
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref=rationale_ref,
    )
    updated = attempt.model_copy(
        update={
            "recovery_decision_id": decision.decision_id,
            "side_effect_boundary_class": SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
            "failure_class": failure_basis,
            "failure_plane": decision.failure_plane,
            "failure_classification": decision.failure_classification,
        }
    )
    await execution_repository.save_attempt_record(record=updated)
    return updated


__all__ = [
    "failure_projection_for_commit_status",
    "publish_failed_commit_recovery_decision",
    "publish_pre_effect_terminal_commit_recovery_decision",
]
