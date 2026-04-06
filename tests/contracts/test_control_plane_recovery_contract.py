# Layer: contract

from __future__ import annotations

import pytest

from orket.core.contracts import CheckpointAcceptanceRecord, ReconciliationRecord, RecoveryDecisionRecord
from orket.core.domain import (
    CheckpointAcceptanceOutcome,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ControlPlaneFailureClass,
    ControlPlaneRecoveryError,
    DivergenceClass,
    ExecutionFailureClass,
    FailurePlane,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResourceFailureClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
    TruthFailureClass,
    build_recovery_decision,
    validate_recovery_decision_authority,
)

pytestmark = pytest.mark.contract


def _accepted_checkpoint(*, resumability_class: CheckpointResumabilityClass) -> CheckpointAcceptanceRecord:
    return CheckpointAcceptanceRecord(
        acceptance_id="accept-1",
        checkpoint_id="checkpoint-1",
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:30:00+00:00",
        outcome=CheckpointAcceptanceOutcome.ACCEPTED,
        resumability_class=resumability_class,
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        evaluated_policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-1",
    )


def _reconciliation() -> ReconciliationRecord:
    return ReconciliationRecord(
        reconciliation_id="recon-1",
        target_ref="run-1",
        comparison_scope="run_scope",
        observed_refs=["obs-1"],
        intended_refs=["intent-1"],
        divergence_class=DivergenceClass.EFFECT_MISSING,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        publication_timestamp="2026-03-23T00:31:00+00:00",
        safe_continuation_class=SafeContinuationClass.OPERATOR_REQUIRED,
    )


def test_recovery_decision_record_accepts_recovery_action_enum() -> None:
    record = RecoveryDecisionRecord(
        decision_id="rd-1",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.START_NEW_ATTEMPT,
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-1",
    )

    assert record.authorized_next_action is RecoveryActionClass.START_NEW_ATTEMPT


def test_validate_recovery_decision_authority_rejects_resume_without_checkpoint_acceptance() -> None:
    decision = RecoveryDecisionRecord(
        decision_id="rd-2",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-2",
    )

    with pytest.raises(ControlPlaneRecoveryError, match="requires checkpoint acceptance"):
        validate_recovery_decision_authority(decision)


def test_validate_recovery_decision_authority_rejects_resume_forbidden_checkpoint() -> None:
    decision = RecoveryDecisionRecord(
        decision_id="rd-3",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-3",
    )

    with pytest.raises(ControlPlaneRecoveryError, match="cannot use resume_forbidden checkpoint"):
        validate_recovery_decision_authority(
            decision,
            checkpoint_acceptance=_accepted_checkpoint(resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN),
        )


def test_build_recovery_decision_accepts_resume_new_attempt_from_checkpoint() -> None:
    decision = build_recovery_decision(
        decision_id="rd-4",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-4",
        checkpoint_acceptance=_accepted_checkpoint(
            resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
        ),
    )

    assert decision.new_attempt_id == "attempt-2"
    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.TOOL_TIMEOUT


def test_build_recovery_decision_keeps_failure_taxonomy_empty_for_unknown_basis() -> None:
    decision = build_recovery_decision(
        decision_id="rd-unknown-basis",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="not_mapped_failure_basis",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref="recovery-receipt-unknown",
    )

    assert decision.failure_plane is None
    assert decision.failure_classification is None


def test_build_recovery_decision_maps_legacy_alias_basis_to_failure_taxonomy() -> None:
    decision = build_recovery_decision(
        decision_id="rd-legacy-basis",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="sandbox_create_failed",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref="recovery-receipt-legacy",
    )

    assert decision.failure_plane is FailurePlane.EXECUTION
    assert decision.failure_classification is ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE


@pytest.mark.parametrize(
    ("basis", "expected_plane", "expected_classification"),
    [
        ("hard_max_age", FailurePlane.RESOURCE, ResourceFailureClass.RESOURCE_UNAVAILABLE),
        ("orphan_detected", FailurePlane.RESOURCE, ResourceFailureClass.ORPHAN_RESOURCE_DETECTED),
        (
            "restart_loop",
            FailurePlane.CONTROL_PLANE,
            ControlPlaneFailureClass.SUPERVISORY_INVARIANT_VIOLATION,
        ),
        ("blocked", FailurePlane.TRUTH, TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY),
    ],
)
def test_build_recovery_decision_maps_sandbox_terminal_aliases(
    basis: str,
    expected_plane: FailurePlane,
    expected_classification: object,
) -> None:
    decision = build_recovery_decision(
        decision_id=f"rd-alias-{basis}",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis=basis,
        side_effect_boundary_class=SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
        rationale_ref="recovery-receipt-alias",
    )

    assert decision.failure_plane is expected_plane
    assert decision.failure_classification is expected_classification


def test_effect_boundary_uncertain_continuation_requires_reconciliation_without_idempotent_retry() -> None:
    decision = RecoveryDecisionRecord(
        decision_id="rd-5",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.START_NEW_ATTEMPT,
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-5",
    )

    with pytest.raises(ControlPlaneRecoveryError, match="requires reconciliation or idempotent retry"):
        validate_recovery_decision_authority(decision)


def test_effect_boundary_uncertain_continuation_allows_reconciliation_or_idempotent_retry() -> None:
    decision = RecoveryDecisionRecord(
        decision_id="rd-6",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RETRY_SAME_ATTEMPT_SCOPE,
        resumed_attempt_id="attempt-1",
        rationale_ref="recovery-receipt-6",
    )

    assert validate_recovery_decision_authority(decision, reconciliation_record=_reconciliation()) is True
    assert validate_recovery_decision_authority(decision, idempotent_retry_permitted=True) is True
