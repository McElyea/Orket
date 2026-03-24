from __future__ import annotations

from collections.abc import Iterable, Sequence

from orket.application.services.control_plane_authority_service import ControlPlaneAuthorityService
from orket.core.contracts import (
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    FinalTruthRecord,
    LeaseRecord,
    OperatorActionRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)


class ControlPlanePublicationService:
    """Application-layer persistence seam for validated ControlPlane records."""

    def __init__(
        self,
        *,
        repository: ControlPlaneRecordRepository,
        authority: ControlPlaneAuthorityService | None = None,
    ) -> None:
        self.repository = repository
        self.authority = authority or ControlPlaneAuthorityService()

    async def append_effect_journal_entry(
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
        contradictory_entry_refs: Sequence[str] = (),
        superseding_entry_refs: Sequence[str] = (),
    ) -> EffectJournalEntryRecord:
        existing_entries = await self.repository.list_effect_journal_entries(run_id=run_id)
        previous_entry = None
        if existing_entries:
            previous_entry = max(existing_entries, key=lambda entry: entry.publication_sequence)
        entry = self.authority.append_effect_journal_entry(
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
        return await self.repository.append_effect_journal_entry(run_id=run_id, entry=entry)

    async def accept_checkpoint(
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
        acceptance = self.authority.accept_checkpoint(
            acceptance_id=acceptance_id,
            checkpoint=checkpoint,
            supervisor_authority_ref=supervisor_authority_ref,
            decision_timestamp=decision_timestamp,
            required_reobservation_class=required_reobservation_class,
            integrity_verification_ref=integrity_verification_ref,
            journal_entries=journal_entries,
            dependent_effect_entry_refs=dependent_effect_entry_refs,
            dependent_reservation_refs=dependent_reservation_refs,
            dependent_lease_refs=dependent_lease_refs,
            reservation_ids=reservation_ids,
            lease_ids=lease_ids,
        )
        return await self.repository.save_checkpoint_acceptance(acceptance=acceptance)

    async def reject_checkpoint(
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
        acceptance = self.authority.reject_checkpoint(
            acceptance_id=acceptance_id,
            checkpoint=checkpoint,
            supervisor_authority_ref=supervisor_authority_ref,
            decision_timestamp=decision_timestamp,
            required_reobservation_class=required_reobservation_class,
            integrity_verification_ref=integrity_verification_ref,
            rejection_reasons=rejection_reasons,
        )
        return await self.repository.save_checkpoint_acceptance(acceptance=acceptance)

    async def publish_recovery_decision(
        self,
        *,
        decision_id: str,
        run_id: str,
        failed_attempt_id: str,
        failure_classification_basis: str,
        side_effect_boundary_class: SideEffectBoundaryClass,
        recovery_policy_ref: str,
        authorized_next_action: RecoveryActionClass,
        rationale_ref: str,
        resumed_attempt_id: str | None = None,
        new_attempt_id: str | None = None,
        target_checkpoint_id: str | None = None,
        required_precondition_refs: list[str] | None = None,
        blocked_actions: list[str] | None = None,
        operator_requirement: object = None,
        checkpoint_acceptance: CheckpointAcceptanceRecord | None = None,
        reconciliation_record: ReconciliationRecord | None = None,
        idempotent_retry_permitted: bool = False,
    ) -> RecoveryDecisionRecord:
        resolved_checkpoint_acceptance = checkpoint_acceptance
        if resolved_checkpoint_acceptance is None and target_checkpoint_id is not None:
            resolved_checkpoint_acceptance = await self.repository.get_checkpoint_acceptance(
                checkpoint_id=target_checkpoint_id
            )
        decision = self.authority.publish_recovery_decision(
            decision_id=decision_id,
            run_id=run_id,
            failed_attempt_id=failed_attempt_id,
            failure_classification_basis=failure_classification_basis,
            side_effect_boundary_class=side_effect_boundary_class,
            recovery_policy_ref=recovery_policy_ref,
            authorized_next_action=authorized_next_action,
            rationale_ref=rationale_ref,
            resumed_attempt_id=resumed_attempt_id,
            new_attempt_id=new_attempt_id,
            target_checkpoint_id=target_checkpoint_id,
            required_precondition_refs=required_precondition_refs,
            blocked_actions=blocked_actions,
            operator_requirement=operator_requirement,
            checkpoint_acceptance=resolved_checkpoint_acceptance,
            reconciliation_record=reconciliation_record,
            idempotent_retry_permitted=idempotent_retry_permitted,
        )
        return await self.repository.save_recovery_decision(decision=decision)

    async def publish_reconciliation(
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
    ) -> ReconciliationRecord:
        record = self.authority.publish_reconciliation(
            reconciliation_id=reconciliation_id,
            target_ref=target_ref,
            comparison_scope=comparison_scope,
            observed_refs=observed_refs,
            intended_refs=intended_refs,
            divergence_class=divergence_class,
            residual_uncertainty_classification=residual_uncertainty_classification,
            publication_timestamp=publication_timestamp,
            safe_continuation_class=safe_continuation_class,
        )
        return await self.repository.save_reconciliation_record(record=record)

    async def publish_lease(
        self,
        *,
        lease_id: str,
        resource_id: str,
        holder_ref: str,
        lease_epoch: int,
        publication_timestamp: str,
        expiry_basis: str,
        status,
        cleanup_eligibility_rule: str,
        granted_timestamp: str | None = None,
        last_confirmed_observation: str | None = None,
        source_reservation_id: str | None = None,
    ) -> LeaseRecord:
        previous_record = await self.repository.get_latest_lease_record(lease_id=lease_id)
        record = self.authority.publish_lease(
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
        return await self.repository.append_lease_record(record=record)

    async def publish_final_truth(
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
        record = self.authority.publish_final_truth(
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
        return await self.repository.save_final_truth(record=record)


__all__ = ["ControlPlanePublicationService"]
