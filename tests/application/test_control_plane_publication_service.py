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
    OperatorActionRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
    ReservationRecord,
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
    OperatorCommandClass,
    OperatorInputClass,
    ReservationKind,
    ReservationStatus,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)


pytestmark = pytest.mark.unit


class InMemoryControlPlaneRecordRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.reservations_by_id: dict[str, list[ReservationRecord]] = {}
        self.journal_by_run: dict[str, list[EffectJournalEntryRecord]] = {}
        self.checkpoint_by_id: dict[str, CheckpointRecord] = {}
        self.acceptance_by_checkpoint: dict[str, CheckpointAcceptanceRecord] = {}
        self.recovery_by_id: dict[str, RecoveryDecisionRecord] = {}
        self.leases_by_id: dict[str, list[LeaseRecord]] = {}
        self.reconciliation_by_id: dict[str, ReconciliationRecord] = {}
        self.operator_action_by_id: dict[str, OperatorActionRecord] = {}
        self.final_truth_by_run: dict[str, FinalTruthRecord] = {}

    async def save_reservation_record(
        self,
        *,
        record: ReservationRecord,
    ) -> ReservationRecord:
        self.reservations_by_id.setdefault(record.reservation_id, []).append(record)
        return record

    async def list_reservation_records(self, *, reservation_id: str) -> list[ReservationRecord]:
        return list(self.reservations_by_id.get(reservation_id, ()))

    async def get_latest_reservation_record(self, *, reservation_id: str) -> ReservationRecord | None:
        records = self.reservations_by_id.get(reservation_id, ())
        return records[-1] if records else None

    async def list_reservation_records_for_holder_ref(self, *, holder_ref: str) -> list[ReservationRecord]:
        matches = [
            record
            for records in self.reservations_by_id.values()
            for record in records
            if record.holder_ref == holder_ref
        ]
        return sorted(matches, key=lambda item: (item.creation_timestamp, item.reservation_id))

    async def get_latest_reservation_record_for_holder_ref(self, *, holder_ref: str) -> ReservationRecord | None:
        matches = await self.list_reservation_records_for_holder_ref(holder_ref=holder_ref)
        return matches[-1] if matches else None

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

    async def save_checkpoint(
        self,
        *,
        record: CheckpointRecord,
    ) -> CheckpointRecord:
        self.checkpoint_by_id[record.checkpoint_id] = record
        return record

    async def get_checkpoint(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        return self.checkpoint_by_id.get(checkpoint_id)

    async def list_checkpoints(self, *, parent_ref: str) -> list[CheckpointRecord]:
        return sorted(
            [record for record in self.checkpoint_by_id.values() if record.parent_ref == parent_ref],
            key=lambda item: (item.creation_timestamp, item.checkpoint_id),
        )

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

    async def list_reconciliation_records(self, *, target_ref: str) -> list[ReconciliationRecord]:
        return sorted(
            [record for record in self.reconciliation_by_id.values() if record.target_ref == target_ref],
            key=lambda item: (item.publication_timestamp, item.reconciliation_id),
        )

    async def get_latest_reconciliation_record(self, *, target_ref: str) -> ReconciliationRecord | None:
        records = await self.list_reconciliation_records(target_ref=target_ref)
        return records[-1] if records else None

    async def save_operator_action(
        self,
        *,
        record: OperatorActionRecord,
    ) -> OperatorActionRecord:
        self.operator_action_by_id[record.action_id] = record
        return record

    async def get_operator_action(self, *, action_id: str) -> OperatorActionRecord | None:
        return self.operator_action_by_id.get(action_id)

    async def list_operator_actions(self, *, target_ref: str) -> list[OperatorActionRecord]:
        return sorted(
            [record for record in self.operator_action_by_id.values() if record.target_ref == target_ref],
            key=lambda item: (item.timestamp, item.action_id),
        )

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
    assert (await repository.get_checkpoint(checkpoint_id="checkpoint-1")) is not None
    assert (await repository.get_recovery_decision(decision_id="rd-1")) is not None


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_checkpoint() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)
    checkpoint = await service.publish_checkpoint(checkpoint=_checkpoint())

    loaded = await repository.get_checkpoint(checkpoint_id=checkpoint.checkpoint_id)
    listed = await repository.list_checkpoints(parent_ref=checkpoint.parent_ref)

    assert loaded is not None
    assert loaded.checkpoint_id == checkpoint.checkpoint_id
    assert listed == [checkpoint]


@pytest.mark.asyncio
async def test_control_plane_publication_service_rejects_recovery_for_missing_checkpoint() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    with pytest.raises(ValueError, match="Checkpoint not found"):
        await service.publish_recovery_decision(
            decision_id="rd-missing-checkpoint",
            run_id="run-1",
            failed_attempt_id="attempt-1",
            failure_classification_basis="tool_timeout",
            side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
            recovery_policy_ref="policy-1",
            authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
            rationale_ref="recovery-receipt-missing-checkpoint",
            target_checkpoint_id="checkpoint-missing",
            new_attempt_id="attempt-2",
        )


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


@pytest.mark.asyncio
async def test_control_plane_publication_service_promotes_reservation_to_lease() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    active = await service.publish_reservation(
        reservation_id="sandbox-reservation:sb-1",
        holder_ref="sandbox-run:run-1",
        reservation_kind=ReservationKind.RESOURCE,
        target_scope_ref="sandbox-allocation:sb-1",
        creation_timestamp="2026-03-24T00:00:00+00:00",
        expiry_or_invalidation_basis="sandbox_create_flow_allocation",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref="sandbox-orchestrator:runner-a:port-allocation",
        promotion_rule="promote_on_lifecycle_record_creation",
    )

    promoted = await service.promote_reservation_to_lease(
        reservation_id=active.reservation_id,
        promoted_lease_id="sandbox-lease:sb-1",
        supervisor_authority_ref="sandbox-lifecycle:sb-1:create_record:runner-a",
        promotion_basis="sandbox_lifecycle_record_created",
    )

    history = await repository.list_reservation_records(reservation_id="sandbox-reservation:sb-1")

    assert active.status is ReservationStatus.ACTIVE
    assert promoted.status is ReservationStatus.PROMOTED_TO_LEASE
    assert promoted.promoted_lease_id == "sandbox-lease:sb-1"
    assert [record.status for record in history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]


@pytest.mark.asyncio
async def test_control_plane_publication_service_releases_and_expires_reservations() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    await service.publish_reservation(
        reservation_id="approval-reservation:apr-1",
        holder_ref="turn-tool-run:sess-1:ISS-1:coder:0001",
        reservation_kind=ReservationKind.OPERATOR_HOLD,
        target_scope_ref="operator-hold:approval-request:apr-1",
        creation_timestamp="2026-03-24T02:00:00+00:00",
        expiry_or_invalidation_basis="pending_tool_approval:write_file",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref="tool-approval-gate:apr-1:create",
    )
    released = await service.release_reservation(
        reservation_id="approval-reservation:apr-1",
        supervisor_authority_ref="tool-approval-gate:apr-1:resolve",
        release_basis="approval_resolved_continue:approved",
    )

    await service.publish_reservation(
        reservation_id="approval-reservation:apr-2",
        holder_ref="turn-tool-run:sess-2:ISS-2:coder:0001",
        reservation_kind=ReservationKind.OPERATOR_HOLD,
        target_scope_ref="operator-hold:approval-request:apr-2",
        creation_timestamp="2026-03-24T02:01:00+00:00",
        expiry_or_invalidation_basis="pending_tool_approval:write_file",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref="tool-approval-gate:apr-2:create",
    )
    expired = await service.expire_reservation(
        reservation_id="approval-reservation:apr-2",
        supervisor_authority_ref="tool-approval-gate:apr-2:resolve",
        expiry_basis="approval_request_expired",
    )

    assert released.status is ReservationStatus.RELEASED
    assert expired.status is ReservationStatus.EXPIRED


@pytest.mark.asyncio
async def test_control_plane_publication_service_persists_operator_action() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ControlPlanePublicationService(repository=repository)

    action = await service.publish_operator_action(
        action_id="op-1",
        actor_ref="api_key_fingerprint:sha256:test",
        input_class=OperatorInputClass.COMMAND,
        target_ref="run-1",
        timestamp="2026-03-24T01:10:00+00:00",
        precondition_basis_ref="sandbox-lifecycle:sb-1:active:3",
        result="accepted",
        command_class=OperatorCommandClass.CANCEL_RUN,
        affected_transition_refs=["sandbox-lifecycle:sb-1:active->cleaned:7"],
        affected_resource_refs=["sandbox-runtime:sb-1"],
        receipt_refs=["truth-1"],
    )

    loaded = await repository.get_operator_action(action_id="op-1")
    listed = await repository.list_operator_actions(target_ref="run-1")

    assert loaded is not None
    assert loaded.command_class is OperatorCommandClass.CANCEL_RUN
    assert listed == [action]
