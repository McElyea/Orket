from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, RecoveryDecisionRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository, ControlPlaneRecordRepository
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
    updated = await execution_repository.save_attempt_record(record=updated)
    return updated


async def publish_pre_effect_terminal_commit_recovery_decision(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    status: str,
    rationale_ref: str,
) -> AttemptRecord:
    failure_basis, failure_plane, failure_classification = failure_projection_for_commit_status(status=status)
    await publication.publish_recovery_decision(
        decision_id=pre_effect_recovery_decision_id(run_id=run.run_id, status=status),
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
    # Abandonment has no execution-failure fields; the decision owns this evidence.
    return attempt


def pre_effect_recovery_decision_id(*, run_id: str, status: str) -> str:
    return f"kernel-action-recovery:{run_id}:{status.lower()}:pre_effect"


async def read_pre_effect_recovery_decision(
    *, repository: ControlPlaneRecordRepository, run: RunRecord, attempt: AttemptRecord,
    statuses: frozenset[str],
) -> RecoveryDecisionRecord | None:
    decisions = []
    for status in sorted(statuses):
        decision_id = pre_effect_recovery_decision_id(run_id=run.run_id, status=status)
        decision = await repository.get_recovery_decision(
            decision_id=decision_id
        )
        if decision is None:
            continue
        basis, plane, classification = failure_projection_for_commit_status(status=status)
        if (decision.decision_id != decision_id or decision.run_id != run.run_id
                or decision.failed_attempt_id != attempt.attempt_id
                or decision.recovery_policy_ref != run.policy_snapshot_id
                or decision.authorized_next_action is not RecoveryActionClass.TERMINATE_RUN
                or decision.side_effect_boundary_class is not SideEffectBoundaryClass.PRE_EFFECT_FAILURE
                or decision.failure_classification_basis != basis
                or decision.failure_plane is not plane or decision.failure_classification is not classification):
            raise ValueError("E_KERNEL_RECOVERY_AUTHORITY_CONFLICT: pre-effect decision binding differs")
        decisions.append(decision)
    if len(decisions) > 1:
        raise ValueError("E_KERNEL_RECOVERY_AUTHORITY_CONFLICT: competing pre-effect decisions")
    return decisions[0] if decisions else None


__all__ = [
    "failure_projection_for_commit_status",
    "publish_failed_commit_recovery_decision",
    "publish_pre_effect_terminal_commit_recovery_decision",
]
