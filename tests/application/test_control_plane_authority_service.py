# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_authority_service import ControlPlaneAuthorityService
from orket.core.contracts import CheckpointRecord, OperatorActionRecord
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    OperatorInputClass,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SideEffectBoundaryClass,
)


pytestmark = pytest.mark.unit


def _service() -> ControlPlaneAuthorityService:
    return ControlPlaneAuthorityService()


def _checkpoint() -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-1",
        parent_ref="attempt-1",
        creation_timestamp="2026-03-23T00:40:00+00:00",
        state_snapshot_ref="snapshot-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:sb-1"],
        dependent_effect_refs=["effect-1"],
        policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
    )


def _operator_mark_terminal() -> OperatorActionRecord:
    return OperatorActionRecord(
        action_id="op-1",
        actor_ref="operator-1",
        input_class=OperatorInputClass.COMMAND,
        target_ref="run-1",
        timestamp="2026-03-23T00:45:00+00:00",
        precondition_basis_ref="recon-1",
        result="accepted",
        command_class=OperatorCommandClass.MARK_TERMINAL,
    )


def test_control_plane_authority_service_appends_effect_journal_chain() -> None:
    service = _service()
    first = service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T00:41:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )
    second = service.append_effect_journal_entry(
        journal_entry_id="journal-2",
        effect_id="effect-2",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-2",
        authorization_basis_ref="auth-2",
        publication_timestamp="2026-03-23T00:42:00+00:00",
        intended_target_ref="resource:sb-2",
        observed_result_ref=None,
        uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        integrity_verification_ref="integrity-2",
        previous_entry=first,
        contradictory_entry_refs=["journal-1"],
    )

    ordered = service.validate_effect_journal_history([second, first])

    assert [entry.publication_sequence for entry in ordered] == [1, 2]
    assert second.prior_journal_entry_id == "journal-1"


def test_control_plane_authority_service_accepts_checkpoint_with_derived_effect_entry_refs() -> None:
    service = _service()
    checkpoint = _checkpoint()
    entry = service.append_effect_journal_entry(
        journal_entry_id="journal-3",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-3",
        authorization_basis_ref="auth-3",
        publication_timestamp="2026-03-23T00:43:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-3",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-3",
    )

    acceptance = service.accept_checkpoint(
        acceptance_id="accept-1",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:44:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
        journal_entries=[entry],
    )

    assert acceptance.dependent_effect_entry_refs == ["journal-3"]


def test_control_plane_authority_service_rejects_checkpoint_as_resume_forbidden() -> None:
    service = _service()
    checkpoint = _checkpoint()

    rejection = service.reject_checkpoint(
        acceptance_id="accept-2",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:44:30+00:00",
        required_reobservation_class=CheckpointReobservationClass.FULL,
        integrity_verification_ref="integrity-checkpoint-1",
        rejection_reasons=["policy_digest_mismatch"],
    )

    assert rejection.resumability_class is CheckpointResumabilityClass.RESUME_FORBIDDEN


def test_control_plane_authority_service_publishes_checkpoint_backed_recovery_decision() -> None:
    service = _service()
    checkpoint = _checkpoint()
    acceptance = service.accept_checkpoint(
        acceptance_id="accept-3",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T00:46:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
        journal_entries=[
            service.append_effect_journal_entry(
                journal_entry_id="journal-4",
                effect_id="effect-1",
                run_id="run-1",
                attempt_id="attempt-1",
                step_id="step-4",
                authorization_basis_ref="auth-4",
                publication_timestamp="2026-03-23T00:45:30+00:00",
                intended_target_ref="resource:sb-1",
                observed_result_ref="receipt-4",
                uncertainty_classification=ResidualUncertaintyClassification.NONE,
                integrity_verification_ref="integrity-4",
            )
        ],
    )

    decision = service.publish_recovery_decision(
        decision_id="rd-1",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
        rationale_ref="recovery-receipt-1",
        checkpoint_acceptance=acceptance,
    )

    assert decision.authorized_next_action is RecoveryActionClass.RESUME_FROM_CHECKPOINT


def test_control_plane_authority_service_publishes_operator_terminal_final_truth() -> None:
    service = _service()

    truth = service.publish_final_truth(
        final_truth_record_id="truth-1",
        run_id="run-1",
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.OPERATOR_TERMINAL_STOP,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        operator_action=_operator_mark_terminal(),
    )

    assert truth.closure_basis is ClosureBasisClassification.OPERATOR_TERMINAL_STOP


def test_control_plane_authority_service_publishes_reconciliation_closed_truth() -> None:
    service = _service()

    truth = service.publish_final_truth(
        final_truth_record_id="truth-2",
        run_id="run-2",
        result_class=ResultClass.DEGRADED,
        completion_classification=CompletionClassification.PARTIAL,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        degradation_classification=DegradationClassification.DECLARED,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[
            AuthoritySourceClass.RECONCILIATION_RECORD,
            AuthoritySourceClass.RECEIPT_EVIDENCE,
        ],
    )

    assert truth.authority_sources[0] is AuthoritySourceClass.RECONCILIATION_RECORD
