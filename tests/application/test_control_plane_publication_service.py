# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import (
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    FinalTruthRecord,
    LeaseRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)


pytestmark = pytest.mark.unit


class InMemoryControlPlaneRecordRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.journal_by_run: dict[str, list[EffectJournalEntryRecord]] = {}
        self.acceptance_by_checkpoint: dict[str, CheckpointAcceptanceRecord] = {}
        self.recovery_by_id: dict[str, RecoveryDecisionRecord] = {}
        self.leases_by_id: dict[str, list[LeaseRecord]] = {}
        self.reconciliation_by_id: dict[str, ReconciliationRecord] = {}
        self.final_truth_by_run: dict[str, FinalTruthRecord] = {}

    async def append_effect_journal_entry(
        self,
        *,
        run_id: str,
        entry: EffectJournalEntryRecord,
    ) -> EffectJournalEntryRecord:
        self.journal_by_run.setdefault(run_id, []).append(entry)
        return entry

    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]:
        return list(self.journal_by_run.get(run_id, ()))

    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord:
        self.acceptance_by_checkpoint[acceptance.checkpoint_id] = acceptance
        return acceptance

    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None:
        return self.acceptance_by_checkpoint.get(checkpoint_id)

    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord:
        self.recovery_by_id[decision.decision_id] = decision
        return decision

    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None:
        return self.recovery_by_id.get(decision_id)

    async def append_lease_record(
        self,
        *,
        record: LeaseRecord,
    ) -> LeaseRecord:
        self.leases_by_id.setdefault(record.lease_id, []).append(record)
        return record

    async def list_lease_records(self, *, lease_id: str) -> list[LeaseRecord]:
        return list(self.leases_by_id.get(lease_id, ()))

    async def get_latest_lease_record(self, *, lease_id: str) -> LeaseRecord | None:
        records = self.leases_by_id.get(lease_id, ())
        return records[-1] if records else None

    async def save_reconciliation_record(
        self,
        *,
        record: ReconciliationRecord,
    ) -> ReconciliationRecord:
        self.reconciliation_by_id[record.reconciliation_id] = record
        return record

    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None:
        return self.reconciliation_by_id.get(reconciliation_id)

    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord:
        self.final_truth_by_run[record.run_id] = record
        return record

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        return self.final_truth_by_run.get(run_id)


def _checkpoint() -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-1",
        parent_ref="attempt-1",
        creation_timestamp="2026-03-23T01:00:00+00:00",
        state_snapshot_ref="snapshot-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:sb-1"],
        dependent_effect_refs=["effect-1"],
        policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
    )


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_journal_sequence() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    first = await service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T01:01:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )
    second = await service.append_effect_journal_entry(
        journal_entry_id="journal-2",
        effect_id="effect-2",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-2",
        authorization_basis_ref="auth-2",
        publication_timestamp="2026-03-23T01:02:00+00:00",
        intended_target_ref="resource:sb-2",
        observed_result_ref=None,
        uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        integrity_verification_ref="integrity-2",
    )

    persisted = await repository.list_effect_journal_entries(run_id="run-1")
    assert first.publication_sequence == 1
    assert second.publication_sequence == 2
    assert len(persisted) == 2


@pytest.mark.asyncio
async def test_control_plane_publication_service_loads_checkpoint_acceptance_for_recovery() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)
    checkpoint = _checkpoint()
    journal_entry = await service.append_effect_journal_entry(
        journal_entry_id="journal-3",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-3",
        authorization_basis_ref="auth-3",
        publication_timestamp="2026-03-23T01:03:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-3",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-3",
    )
    await service.accept_checkpoint(
        acceptance_id="accept-1",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T01:04:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
        journal_entries=[journal_entry],
    )

    decision = await service.publish_recovery_decision(
        decision_id="rd-1",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        rationale_ref="recovery-receipt-1",
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
    )

    assert decision.target_checkpoint_id == "checkpoint-1"
    assert (await repository.get_recovery_decision(decision_id="rd-1")) is not None


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_final_truth() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    record = await service.publish_final_truth(
        final_truth_record_id="truth-1",
        run_id="run-1",
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

    assert record.run_id == "run-1"
    assert (await repository.get_final_truth(run_id="run-1")) is not None


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_reconciliation_record() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    record = await service.publish_reconciliation(
        reconciliation_id="recon-1",
        target_ref="run-1",
        comparison_scope="run_scope",
        observed_refs=["obs-1"],
        intended_refs=["intent-1"],
        divergence_class=DivergenceClass.RESOURCE_STATE_DIVERGED,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp="2026-03-23T01:10:00+00:00",
        safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
    )

    assert record.reconciliation_id == "recon-1"
    assert (await repository.get_reconciliation_record(reconciliation_id="recon-1")) is not None


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_append_only_lease_history() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    first = await service.publish_lease(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:00:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:05:00+00:00",
        status=LeaseStatus.ACTIVE,
        last_confirmed_observation="sandbox-lifecycle:sb-1:creating:1",
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )
    second = await service.publish_lease(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:02:00+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:07:00+00:00",
        status=LeaseStatus.ACTIVE,
        last_confirmed_observation="sandbox-lifecycle:sb-1:active:2",
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )

    history = await repository.list_lease_records(lease_id="sandbox-lease:sb-1")

    assert first.granted_timestamp == "2026-03-23T01:00:00+00:00"
    assert second.granted_timestamp == first.granted_timestamp
    assert len(history) == 2
    assert history[-1].history_refs
