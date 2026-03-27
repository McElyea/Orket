from __future__ import annotations

from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import (
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    ControlPlaneFailureClass,
    ExecutionFailureClass,
    FailurePlane,
    ProtocolFailureClass,
    RecoveryActionClass,
    ResourceFailureClass,
    SideEffectBoundaryClass,
    TruthFailureClass,
)

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_effect_journal_models import CheckpointAcceptanceRecord
    from orket.core.contracts.control_plane_models import ReconciliationRecord, RecoveryDecisionRecord


CONTINUATION_ACTIONS = frozenset(
    {
        RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE,
        RecoveryActionClass.START_NEW_ATTEMPT,
        RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        RecoveryActionClass.DOWNGRADE_TO_DEGRADED_MODE,
    }
)


class ControlPlaneRecoveryError(ValueError):
    """Raised when a recovery decision exceeds recovery authority."""


FailureClassification = (
    ExecutionFailureClass
    | ProtocolFailureClass
    | TruthFailureClass
    | ResourceFailureClass
    | ControlPlaneFailureClass
)
_FAILURE_CLASSIFICATION_LOOKUP: dict[str, tuple[FailurePlane, FailureClassification]] = {
    **{item.value: (FailurePlane.EXECUTION, item) for item in ExecutionFailureClass},
    **{item.value: (FailurePlane.PROTOCOL, item) for item in ProtocolFailureClass},
    **{item.value: (FailurePlane.TRUTH, item) for item in TruthFailureClass},
    **{item.value: (FailurePlane.RESOURCE, item) for item in ResourceFailureClass},
    **{item.value: (FailurePlane.CONTROL_PLANE, item) for item in ControlPlaneFailureClass},
}
# Transitional aliases keep current-state failure basis tokens mappable during packet-v2 migration.
_FAILURE_CLASSIFICATION_ALIASES: dict[str, tuple[FailurePlane, FailureClassification]] = {
    "sandbox_create_failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "sandbox_start_failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "create_failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "start_failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "blocked": (FailurePlane.TRUTH, TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY),
    "restart_loop": (
        FailurePlane.CONTROL_PLANE,
        ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
    ),
    "orphan_detected": (FailurePlane.RESOURCE, ResourceFailureClass.ORPHAN_RESOURCE_DETECTED),
    "orphan_unverified_ownership": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_STATE_UNCERTAIN),
    "hard_max_age": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_UNAVAILABLE),
    "cleaned_externally": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_STATE_UNCERTAIN),
    "tool_execution_failed": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "gitea_state_worker_failure": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "gitea_state_claim_failure": (FailurePlane.EXECUTION, ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE),
    "lease_expired": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_UNAVAILABLE),
    "control_plane_resource_drift": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_STATE_UNCERTAIN),
    "lost_runtime": (FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_STATE_UNCERTAIN),
    "unfinished_pre_effect_attempt": (
        FailurePlane.CONTROL_PLANE,
        ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
    ),
    "unfinished_post_effect_attempt": (
        FailurePlane.CONTROL_PLANE,
        ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
    ),
    "unfinished_effect_boundary_uncertain_attempt": (
        FailurePlane.CONTROL_PLANE,
        ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
    ),
    "reconciliation_closed_unexpected_effect_observed": (
        FailurePlane.TRUTH,
        TruthFailureClass.TOOL_RESULT_CONTRADICTION,
    ),
    "reconciliation_closed_insufficient_observation": (
        FailurePlane.TRUTH,
        TruthFailureClass.MISSING_REQUIRED_EVIDENCE,
    ),
    "tool_execution_blocked": (FailurePlane.TRUTH, TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY),
}


def infer_failure_taxonomy(
    *,
    failure_classification_basis: str,
) -> tuple[FailurePlane | None, FailureClassification | None]:
    normalized = str(failure_classification_basis or "").strip().lower()
    if not normalized:
        return None, None
    resolved = _FAILURE_CLASSIFICATION_LOOKUP.get(normalized)
    if resolved is not None:
        return resolved
    return _FAILURE_CLASSIFICATION_ALIASES.get(normalized, (None, None))


def validate_recovery_decision_authority(
    decision: "RecoveryDecisionRecord",
    *,
    checkpoint_acceptance: "CheckpointAcceptanceRecord | None" = None,
    reconciliation_record: "ReconciliationRecord | None" = None,
    idempotent_retry_permitted: bool = False,
) -> bool:
    action = decision.authorized_next_action
    has_resumed_attempt = decision.resumed_attempt_id is not None
    has_new_attempt = decision.new_attempt_id is not None

    if action is RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE and (not has_resumed_attempt or has_new_attempt):
        raise ControlPlaneRecoveryError("retry_same_attempt_scope requires resumed_attempt_id only")
    if action is RecoveryActionClass.START_NEW_ATTEMPT and (not has_new_attempt or has_resumed_attempt):
        raise ControlPlaneRecoveryError("start_new_attempt requires new_attempt_id only")
    if action in {
        RecoveryActionClass.REQUIRE_OBSERVATION_THEN_CONTINUE,
        RecoveryActionClass.REQUIRE_RECONCILIATION_THEN_DECIDE,
        RecoveryActionClass.PERFORM_CONTROL_PLANE_RECOVERY_ACTION,
        RecoveryActionClass.QUARANTINE_RUN,
        RecoveryActionClass.ESCALATE_TO_OPERATOR,
        RecoveryActionClass.TERMINATE_RUN,
    } and (has_resumed_attempt or has_new_attempt):
        raise ControlPlaneRecoveryError(f"{action.value} must not publish execution target ids")

    if action is RecoveryActionClass.DOWNGRADE_TO_DEGRADED_MODE and (has_resumed_attempt == has_new_attempt):
        raise ControlPlaneRecoveryError("downgrade_to_degraded_mode requires exactly one execution target")

    if action is not RecoveryActionClass.RESUME_FROM_CHECKPOINT and decision.target_checkpoint_id is not None:
        raise ControlPlaneRecoveryError("target_checkpoint_id is only valid for resume_from_checkpoint")

    if action is RecoveryActionClass.RESUME_FROM_CHECKPOINT:
        if decision.target_checkpoint_id is None:
            raise ControlPlaneRecoveryError("resume_from_checkpoint requires target_checkpoint_id")
        if checkpoint_acceptance is None:
            raise ControlPlaneRecoveryError("resume_from_checkpoint requires checkpoint acceptance")
        if checkpoint_acceptance.checkpoint_id != decision.target_checkpoint_id:
            raise ControlPlaneRecoveryError("checkpoint acceptance must match recovery target_checkpoint_id")
        if checkpoint_acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED:
            raise ControlPlaneRecoveryError("resume_from_checkpoint requires accepted checkpoint")
        if checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN:
            raise ControlPlaneRecoveryError("resume_from_checkpoint cannot use resume_forbidden checkpoint")
        if checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT:
            if not has_resumed_attempt or has_new_attempt:
                raise ControlPlaneRecoveryError("resume_same_attempt checkpoint requires resumed_attempt_id only")
        if checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT:
            if not has_new_attempt or has_resumed_attempt:
                raise ControlPlaneRecoveryError("resume_new_attempt checkpoint requires new_attempt_id only")

    if (
        decision.side_effect_boundary_class is SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
        and action in CONTINUATION_ACTIONS
        and not idempotent_retry_permitted
        and reconciliation_record is None
    ):
        raise ControlPlaneRecoveryError("effect_boundary_uncertain continuation requires reconciliation or idempotent retry")
    return True


def build_recovery_decision(
    *,
    decision_id: str,
    run_id: str,
    failed_attempt_id: str,
    failure_classification_basis: str,
    failure_plane: FailurePlane | None = None,
    failure_classification: FailureClassification | None = None,
    side_effect_boundary_class: SideEffectBoundaryClass,
    recovery_policy_ref: str,
    authorized_next_action: RecoveryActionClass,
    resumed_attempt_id: str | None = None,
    new_attempt_id: str | None = None,
    target_checkpoint_id: str | None = None,
    required_precondition_refs: list[str] | None = None,
    blocked_actions: list[str] | None = None,
    operator_requirement: object = None,
    rationale_ref: str,
    checkpoint_acceptance: "CheckpointAcceptanceRecord | None" = None,
    reconciliation_record: "ReconciliationRecord | None" = None,
    idempotent_retry_permitted: bool = False,
) -> "RecoveryDecisionRecord":
    from orket.core.contracts.control_plane_models import RecoveryDecisionRecord

    resolved_failure_plane = failure_plane
    resolved_failure_classification = failure_classification
    if resolved_failure_plane is None and resolved_failure_classification is None:
        resolved_failure_plane, resolved_failure_classification = infer_failure_taxonomy(
            failure_classification_basis=failure_classification_basis
        )
    elif (resolved_failure_plane is None) != (resolved_failure_classification is None):
        raise ControlPlaneRecoveryError("failure_plane and failure_classification must be set together")

    decision = RecoveryDecisionRecord(
        decision_id=decision_id,
        run_id=run_id,
        failed_attempt_id=failed_attempt_id,
        failure_classification_basis=failure_classification_basis,
        failure_plane=resolved_failure_plane,
        failure_classification=resolved_failure_classification,
        side_effect_boundary_class=side_effect_boundary_class,
        recovery_policy_ref=recovery_policy_ref,
        authorized_next_action=authorized_next_action,
        resumed_attempt_id=resumed_attempt_id,
        new_attempt_id=new_attempt_id,
        target_checkpoint_id=target_checkpoint_id,
        required_precondition_refs=required_precondition_refs or [],
        blocked_actions=blocked_actions or [],
        operator_requirement=operator_requirement,
        rationale_ref=rationale_ref,
    )
    validate_recovery_decision_authority(
        decision,
        checkpoint_acceptance=checkpoint_acceptance,
        reconciliation_record=reconciliation_record,
        idempotent_retry_permitted=idempotent_retry_permitted,
    )
    return decision


__all__ = [
    "CONTINUATION_ACTIONS",
    "ControlPlaneRecoveryError",
    "build_recovery_decision",
    "infer_failure_taxonomy",
    "validate_recovery_decision_authority",
]
