# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_reconciliation_service import (
    SandboxControlPlaneReconciliationError,
    SandboxControlPlaneReconciliationService,
)
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
    ClosureBasisClassification,
    DivergenceClass,
    LeaseStatus,
    ResultClass,
    SafeContinuationClass,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


pytestmark = pytest.mark.unit


class ReconciliationRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.reservations_by_id: dict[str, list[ReservationRecord]] = {}
        self.leases_by_id: dict[str, list[LeaseRecord]] = {}
        self.reconciliation_by_id: dict[str, ReconciliationRecord] = {}
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
        return []

    async def get_latest_reservation_record_for_holder_ref(self, *, holder_ref: str) -> ReservationRecord | None:
        return None

    async def append_effect_journal_entry(
        self,
        *,
        run_id: str,
        entry: EffectJournalEntryRecord,
    ) -> EffectJournalEntryRecord:
        raise NotImplementedError

    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]:
        raise NotImplementedError

    async def save_checkpoint(
        self,
        *,
        record: CheckpointRecord,
    ) -> CheckpointRecord:
        raise NotImplementedError

    async def get_checkpoint(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        raise NotImplementedError

    async def list_checkpoints(self, *, parent_ref: str) -> list[CheckpointRecord]:
        raise NotImplementedError

    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord:
        raise NotImplementedError

    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None:
        raise NotImplementedError

    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord:
        raise NotImplementedError

    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None:
        raise NotImplementedError

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
        return record

    async def get_operator_action(self, *, action_id: str) -> OperatorActionRecord | None:
        return None

    async def list_operator_actions(self, *, target_ref: str) -> list[OperatorActionRecord]:
        return []

    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord:
        self.final_truth_by_run[record.run_id] = record
        return record

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        return self.final_truth_by_run.get(run_id)


def _record(*, terminal_reason: TerminalReason) -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        owner_instance_id="runner-a",
        lease_epoch=1,
        lease_expires_at="2026-03-23T01:05:00+00:00",
        state=SandboxState.TERMINAL,
        cleanup_state=CleanupState.NONE,
        record_version=4,
        created_at="2026-03-23T01:00:00+00:00",
        last_heartbeat_at="2026-03-23T01:00:30+00:00",
        terminal_at="2026-03-23T01:02:00+00:00",
        terminal_reason=terminal_reason,
        cleanup_due_at="2026-03-23T01:12:00+00:00",
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_sandbox_control_plane_reconciliation_service_publishes_lost_runtime_closure() -> None:
    repository = ReconciliationRepository()
    service = SandboxControlPlaneReconciliationService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    published = await service.publish_lost_runtime_reconciliation(
        record=_record(terminal_reason=TerminalReason.LOST_RUNTIME),
        observed_at="2026-03-23T01:10:00+00:00",
    )

    assert published.reconciliation_record.target_ref == "run-1"
    lease = await repository.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    assert lease is not None
    assert lease.status is LeaseStatus.UNCERTAIN
    assert published.final_truth is not None
    assert published.final_truth.result_class is ResultClass.BLOCKED
    assert published.final_truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED


@pytest.mark.asyncio
async def test_sandbox_control_plane_reconciliation_service_rejects_non_lost_runtime_record() -> None:
    repository = ReconciliationRepository()
    service = SandboxControlPlaneReconciliationService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    with pytest.raises(
        SandboxControlPlaneReconciliationError,
        match="requires terminal_reason=lost_runtime",
    ):
        await service.publish_lost_runtime_reconciliation(
            record=_record(terminal_reason=TerminalReason.SUCCESS),
            observed_at="2026-03-23T01:10:00+00:00",
        )


@pytest.mark.asyncio
async def test_sandbox_control_plane_reconciliation_service_publishes_reclaimable_reconciliation() -> None:
    repository = ReconciliationRepository()
    service = SandboxControlPlaneReconciliationService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    published = await service.publish_reclaimable_reconciliation(
        record=_record(terminal_reason=TerminalReason.LEASE_EXPIRED).model_copy(
            update={"state": SandboxState.RECLAIMABLE}
        ),
        observed_at="2026-03-23T01:10:00+00:00",
    )

    assert published.final_truth is None
    lease = await repository.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    assert lease is not None
    assert lease.status is LeaseStatus.EXPIRED
    assert published.reconciliation_record.divergence_class is DivergenceClass.OWNERSHIP_DIVERGED
    assert published.reconciliation_record.safe_continuation_class is SafeContinuationClass.UNSAFE_TO_CONTINUE
