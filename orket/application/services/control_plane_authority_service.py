from __future__ import annotations

from collections.abc import Iterable, Sequence

from orket.core.contracts import (
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    FinalTruthRecord,
    LeaseRecord,
    OperatorActionRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
    ReservationRecord,
    ResourceRecord,
)
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointAcceptanceOutcome,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    CleanupAuthorityClass,
    ClosureBasisClassification,
    CompletionClassification,
    ControlPlaneFailureClass,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    ExecutionFailureClass,
    FailurePlane,
    LeaseStatus,
    OperatorCommandClass,
    OperatorInputClass,
    OrphanClassification,
    OwnershipClass,
    ProtocolFailureClass,
    RecoveryActionClass,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResourceFailureClass,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
    TruthFailureClass,
    build_final_truth_record,
    build_lease_record,
    build_recovery_decision,
    build_reservation_record,
    create_effect_journal_entry,
    validate_checkpoint_acceptance,
    validate_effect_journal_chain,
)


class ControlPlaneAuthorityService:
    """Application-layer seam for validated control-plane record publication."""

    def append_effect_journal_entry(
        self,
        *,
        journal_entry_id: str,
        effect_id: str,
        run_id: str,
        attempt_id: str,
        step_id: str,
        authorization_basis_ref: str,
        publication_timestamp: str,
        intended_target_ref: str,
        observed_result_ref: str | None,
        uncertainty_classification: ResidualUncertaintyClassification,
        integrity_verification_ref: str,
        previous_entry: EffectJournalEntryRecord | None = None,
        contradictory_entry_refs: Sequence[str] = (),
        superseding_entry_refs: Sequence[str] = (),
    ) -> EffectJournalEntryRecord:
        return create_effect_journal_entry(
            journal_entry_id=journal_entry_id,
            effect_id=effect_id,
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step_id,
            authorization_basis_ref=authorization_basis_ref,
            publication_timestamp=publication_timestamp,
            intended_target_ref=intended_target_ref,
            observed_result_ref=observed_result_ref,
            uncertainty_classification=uncertainty_classification,
            integrity_verification_ref=integrity_verification_ref,
            previous_entry=previous_entry,
            contradictory_entry_refs=contradictory_entry_refs,
            superseding_entry_refs=superseding_entry_refs,
        )

    def validate_effect_journal_history(
        self,
        entries: Iterable[EffectJournalEntryRecord],
    ) -> tuple[EffectJournalEntryRecord, ...]:
        return validate_effect_journal_chain(entries)

    def accept_checkpoint(
        self,
        *,
        acceptance_id: str,
        checkpoint: CheckpointRecord,
        supervisor_authority_ref: str,
        decision_timestamp: str,
        required_reobservation_class: CheckpointReobservationClass,
        integrity_verification_ref: str,
        journal_entries: Iterable[EffectJournalEntryRecord] = (),
        dependent_effect_entry_refs: Sequence[str] | None = None,
        dependent_reservation_refs: Sequence[str] = (),
        dependent_lease_refs: Sequence[str] = (),
        reservation_ids: Iterable[str] | None = None,
        lease_ids: Iterable[str] | None = None,
    ) -> CheckpointAcceptanceRecord:
        journal_entries = tuple(journal_entries)
        acceptance = CheckpointAcceptanceRecord(
            acceptance_id=acceptance_id,
            checkpoint_id=checkpoint.checkpoint_id,
            supervisor_authority_ref=supervisor_authority_ref,
            decision_timestamp=decision_timestamp,
            outcome=CheckpointAcceptanceOutcome.ACCEPTED,
            resumability_class=checkpoint.resumability_class,
            required_reobservation_class=required_reobservation_class,
            evaluated_policy_digest=checkpoint.policy_digest,
            integrity_verification_ref=integrity_verification_ref,
            dependent_effect_entry_refs=list(dependent_effect_entry_refs or [e.journal_entry_id for e in journal_entries]),
            dependent_reservation_refs=list(dependent_reservation_refs),
            dependent_lease_refs=list(dependent_lease_refs),
        )
        validate_checkpoint_acceptance(
            checkpoint,
            acceptance,
            journal_entries=journal_entries,
            reservation_ids=reservation_ids,
            lease_ids=lease_ids,
        )
        return acceptance

    def reject_checkpoint(
        self,
        *,
        acceptance_id: str,
        checkpoint: CheckpointRecord,
        supervisor_authority_ref: str,
        decision_timestamp: str,
        required_reobservation_class: CheckpointReobservationClass,
        integrity_verification_ref: str,
        rejection_reasons: Sequence[str],
    ) -> CheckpointAcceptanceRecord:
        return CheckpointAcceptanceRecord(
            acceptance_id=acceptance_id,
            checkpoint_id=checkpoint.checkpoint_id,
            supervisor_authority_ref=supervisor_authority_ref,
            decision_timestamp=decision_timestamp,
            outcome=CheckpointAcceptanceOutcome.REJECTED,
            resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
            required_reobservation_class=required_reobservation_class,
            evaluated_policy_digest=checkpoint.policy_digest,
            integrity_verification_ref=integrity_verification_ref,
            rejection_reasons=list(rejection_reasons),
        )

    def publish_recovery_decision(
        self,
        *,
        decision_id: str,
        run_id: str,
        failed_attempt_id: str,
        failure_classification_basis: str,
        failure_plane: FailurePlane | None = None,
        failure_classification: (
            ExecutionFailureClass
            | ProtocolFailureClass
            | TruthFailureClass
            | ResourceFailureClass
            | ControlPlaneFailureClass
            | None
        ) = None,
        side_effect_boundary_class: SideEffectBoundaryClass,
        recovery_policy_ref: str,
        authorized_next_action: RecoveryActionClass,
        rationale_ref: str,
        resumed_attempt_id: str | None = None,
        new_attempt_id: str | None = None,
        target_checkpoint_id: str | None = None,
        required_precondition_refs: list[str] | None = None,
        blocked_actions: list[str] | None = None,
        operator_requirement: OperatorCommandClass | None = None,
        checkpoint_acceptance: CheckpointAcceptanceRecord | None = None,
        reconciliation_record: ReconciliationRecord | None = None,
        idempotent_retry_permitted: bool = False,
    ) -> RecoveryDecisionRecord:
        return build_recovery_decision(
            decision_id=decision_id,
            run_id=run_id,
            failed_attempt_id=failed_attempt_id,
            failure_classification_basis=failure_classification_basis,
            failure_plane=failure_plane,
            failure_classification=failure_classification,
            side_effect_boundary_class=side_effect_boundary_class,
            recovery_policy_ref=recovery_policy_ref,
            authorized_next_action=authorized_next_action,
            resumed_attempt_id=resumed_attempt_id,
            new_attempt_id=new_attempt_id,
            target_checkpoint_id=target_checkpoint_id,
            required_precondition_refs=required_precondition_refs,
            blocked_actions=blocked_actions,
            operator_requirement=operator_requirement,
            rationale_ref=rationale_ref,
            checkpoint_acceptance=checkpoint_acceptance,
            reconciliation_record=reconciliation_record,
            idempotent_retry_permitted=idempotent_retry_permitted,
        )

    def publish_reconciliation(
        self,
        *,
        reconciliation_id: str,
        target_ref: str,
        comparison_scope: str,
        observed_refs: list[str] | None = None,
        intended_refs: list[str] | None = None,
        divergence_class: DivergenceClass,
        residual_uncertainty_classification: ResidualUncertaintyClassification,
        publication_timestamp: str,
        safe_continuation_class: SafeContinuationClass,
        operator_requirement: OperatorCommandClass | None = None,
    ) -> ReconciliationRecord:
        return ReconciliationRecord(
            reconciliation_id=reconciliation_id,
            target_ref=target_ref,
            comparison_scope=comparison_scope,
            observed_refs=list(observed_refs or ()),
            intended_refs=list(intended_refs or ()),
            divergence_class=divergence_class,
            residual_uncertainty_classification=residual_uncertainty_classification,
            publication_timestamp=publication_timestamp,
            safe_continuation_class=safe_continuation_class,
            operator_requirement=operator_requirement,
        )

    def publish_reservation(
        self,
        *,
        reservation_id: str,
        holder_ref: str,
        reservation_kind: ReservationKind,
        target_scope_ref: str,
        creation_timestamp: str,
        expiry_or_invalidation_basis: str,
        status: ReservationStatus,
        supervisor_authority_ref: str,
        promotion_rule: str | None = None,
        promoted_lease_id: str | None = None,
        previous_record: ReservationRecord | None = None,
    ) -> ReservationRecord:
        return build_reservation_record(
            reservation_id=reservation_id,
            holder_ref=holder_ref,
            reservation_kind=reservation_kind,
            target_scope_ref=target_scope_ref,
            creation_timestamp=creation_timestamp,
            expiry_or_invalidation_basis=expiry_or_invalidation_basis,
            status=status,
            supervisor_authority_ref=supervisor_authority_ref,
            promotion_rule=promotion_rule,
            promoted_lease_id=promoted_lease_id,
            previous_record=previous_record,
        )

    def publish_lease(
        self,
        *,
        lease_id: str,
        resource_id: str,
        holder_ref: str,
        lease_epoch: int,
        publication_timestamp: str,
        expiry_basis: str,
        status: LeaseStatus,
        cleanup_eligibility_rule: str,
        granted_timestamp: str | None = None,
        last_confirmed_observation: str | None = None,
        source_reservation_id: str | None = None,
        previous_record: LeaseRecord | None = None,
    ) -> LeaseRecord:
        return build_lease_record(
            lease_id=lease_id,
            resource_id=resource_id,
            holder_ref=holder_ref,
            lease_epoch=lease_epoch,
            publication_timestamp=publication_timestamp,
            expiry_basis=expiry_basis,
            status=status,
            cleanup_eligibility_rule=cleanup_eligibility_rule,
            granted_timestamp=granted_timestamp,
            last_confirmed_observation=last_confirmed_observation,
            source_reservation_id=source_reservation_id,
            previous_record=previous_record,
        )

    def publish_resource(
        self,
        *,
        resource_id: str,
        resource_kind: str,
        namespace_scope: str,
        ownership_class: OwnershipClass,
        current_observed_state: str,
        last_observed_timestamp: str,
        cleanup_authority_class: CleanupAuthorityClass,
        provenance_ref: str,
        reconciliation_status: str,
        orphan_classification: OrphanClassification,
    ) -> ResourceRecord:
        return ResourceRecord(
            resource_id=resource_id,
            resource_kind=resource_kind,
            namespace_scope=namespace_scope,
            ownership_class=ownership_class,
            current_observed_state=current_observed_state,
            last_observed_timestamp=last_observed_timestamp,
            cleanup_authority_class=cleanup_authority_class,
            provenance_ref=provenance_ref,
            reconciliation_status=reconciliation_status,
            orphan_classification=orphan_classification,
        )

    def publish_final_truth(
        self,
        *,
        final_truth_record_id: str,
        run_id: str,
        result_class: ResultClass,
        completion_classification: CompletionClassification,
        evidence_sufficiency_classification: EvidenceSufficiencyClassification,
        residual_uncertainty_classification: ResidualUncertaintyClassification,
        degradation_classification: DegradationClassification,
        closure_basis: ClosureBasisClassification,
        authority_sources: list[AuthoritySourceClass],
        authoritative_result_ref: str | None = None,
        operator_action: OperatorActionRecord | None = None,
    ) -> FinalTruthRecord:
        return build_final_truth_record(
            final_truth_record_id=final_truth_record_id,
            run_id=run_id,
            result_class=result_class,
            completion_classification=completion_classification,
            evidence_sufficiency_classification=evidence_sufficiency_classification,
            residual_uncertainty_classification=residual_uncertainty_classification,
            degradation_classification=degradation_classification,
            closure_basis=closure_basis,
            authority_sources=authority_sources,
            authoritative_result_ref=authoritative_result_ref,
            operator_action=operator_action,
        )

    def publish_operator_action(
        self,
        *,
        action_id: str,
        actor_ref: str,
        input_class: OperatorInputClass,
        target_ref: str,
        timestamp: str,
        precondition_basis_ref: str,
        result: str,
        command_class: OperatorCommandClass | None = None,
        risk_acceptance_scope: str | None = None,
        attestation_scope: str | None = None,
        attestation_payload: dict[str, object] | None = None,
        affected_transition_refs: list[str] | None = None,
        affected_resource_refs: list[str] | None = None,
        receipt_refs: list[str] | None = None,
    ) -> OperatorActionRecord:
        return OperatorActionRecord(
            action_id=action_id,
            actor_ref=actor_ref,
            input_class=input_class,
            target_ref=target_ref,
            timestamp=timestamp,
            precondition_basis_ref=precondition_basis_ref,
            result=result,
            command_class=command_class,
            risk_acceptance_scope=risk_acceptance_scope,
            attestation_scope=attestation_scope,
            attestation_payload=dict(attestation_payload or {}),
            affected_transition_refs=list(affected_transition_refs or ()),
            affected_resource_refs=list(affected_resource_refs or ()),
            receipt_refs=list(receipt_refs or ()),
        )


__all__ = ["ControlPlaneAuthorityService"]
