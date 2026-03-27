# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_lease_service import SandboxControlPlaneLeaseService
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
from orket.core.contracts.repositories import ControlPlaneRecordRepository
from orket.core.domain import LeaseStatus
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


pytestmark = pytest.mark.unit


class LeaseOnlyRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.reservations_by_id: dict[str, list[ReservationRecord]] = {}
        self.resources_by_id: dict[str, list[ResourceRecord]] = {}
        self.leases_by_id: dict[str, list[LeaseRecord]] = {}

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

    async def save_resource_record(
        self,
        *,
        record: ResourceRecord,
    ) -> ResourceRecord:
        self.resources_by_id.setdefault(record.resource_id, []).append(record)
        return record

    async def list_resource_records(self, *, resource_id: str) -> list[ResourceRecord]:
        return list(self.resources_by_id.get(resource_id, ()))

    async def get_latest_resource_record(self, *, resource_id: str) -> ResourceRecord | None:
        records = self.resources_by_id.get(resource_id, ())
        return records[-1] if records else None

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
        raise NotImplementedError

    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None:
        raise NotImplementedError

    async def list_reconciliation_records(self, *, target_ref: str) -> list[ReconciliationRecord]:
        raise NotImplementedError

    async def get_latest_reconciliation_record(self, *, target_ref: str) -> ReconciliationRecord | None:
        raise NotImplementedError

    async def save_operator_action(
        self,
        *,
        record: OperatorActionRecord,
    ) -> OperatorActionRecord:
        raise NotImplementedError

    async def get_operator_action(self, *, action_id: str) -> OperatorActionRecord | None:
        raise NotImplementedError

    async def list_operator_actions(self, *, target_ref: str) -> list[OperatorActionRecord]:
        raise NotImplementedError

    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord:
        raise NotImplementedError

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        raise NotImplementedError


def _active_record() -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        owner_instance_id="runner-a",
        lease_epoch=1,
        lease_expires_at="2026-03-23T01:05:00+00:00",
        state=SandboxState.ACTIVE,
        cleanup_state=CleanupState.NONE,
        record_version=3,
        created_at="2026-03-23T01:00:00+00:00",
        last_heartbeat_at="2026-03-23T01:00:30+00:00",
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_sandbox_control_plane_lease_service_reuses_same_second_same_status_publication() -> None:
    repository = LeaseOnlyRepository()
    service = SandboxControlPlaneLeaseService(
        publication=ControlPlanePublicationService(repository=repository)
    )
    record = _active_record()

    first = await service.publish_from_record(
        record=record,
        publication_timestamp="2026-03-23T01:00:30+00:00",
    )
    second = await service.publish_from_record(
        record=record,
        publication_timestamp="2026-03-23T01:00:30+00:00",
    )

    history = await repository.list_lease_records(lease_id="sandbox-lease:sb-1")

    assert first.status is LeaseStatus.ACTIVE
    assert second.publication_timestamp == first.publication_timestamp
    assert len(history) == 1
