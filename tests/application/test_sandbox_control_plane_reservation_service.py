# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_reservation_service import (
    SandboxControlPlaneReservationService,
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
    ResourceRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository
from orket.core.domain import ReservationStatus
from orket.domain.sandbox import PortAllocation


pytestmark = pytest.mark.unit


class ReservationOnlyRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.reservations_by_id: dict[str, list[ReservationRecord]] = {}
        self.resources_by_id: dict[str, list[ResourceRecord]] = {}

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
        return entry

    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]:
        return []

    async def save_checkpoint(
        self,
        *,
        record: CheckpointRecord,
    ) -> CheckpointRecord:
        return record

    async def get_checkpoint(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        return None

    async def list_checkpoints(self, *, parent_ref: str) -> list[CheckpointRecord]:
        return []

    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord:
        return acceptance

    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None:
        return None

    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord:
        return decision

    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None:
        return None

    async def append_lease_record(
        self,
        *,
        record: LeaseRecord,
    ) -> LeaseRecord:
        return record

    async def list_lease_records(self, *, lease_id: str) -> list[LeaseRecord]:
        return []

    async def get_latest_lease_record(self, *, lease_id: str) -> LeaseRecord | None:
        return None

    async def save_reconciliation_record(
        self,
        *,
        record: ReconciliationRecord,
    ) -> ReconciliationRecord:
        return record

    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None:
        return None

    async def list_reconciliation_records(self, *, target_ref: str) -> list[ReconciliationRecord]:
        return []

    async def get_latest_reconciliation_record(self, *, target_ref: str) -> ReconciliationRecord | None:
        return None

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
        return record

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        return None


@pytest.mark.asyncio
async def test_sandbox_reservation_service_publishes_and_promotes_allocation_reservation() -> None:
    repository = ReservationOnlyRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = SandboxControlPlaneReservationService(publication=publication)

    active = await service.publish_allocation_reservation(
        sandbox_id="sb-1",
        run_id="run-1",
        compose_project="orket-sandbox-run-1",
        ports=PortAllocation(api=8001, frontend=3001, database=5433, admin_tool=8081),
        creation_timestamp="2026-03-24T00:00:00+00:00",
        instance_id="runner-a",
    )
    promoted = await service.promote_allocation_reservation(
        sandbox_id="sb-1",
        instance_id="runner-a",
    )

    history = await repository.list_reservation_records(reservation_id=active.reservation_id)

    assert active.status is ReservationStatus.ACTIVE
    assert promoted.status is ReservationStatus.PROMOTED_TO_LEASE
    assert promoted.promoted_lease_id == "sandbox-lease:sb-1"
    assert [record.status for record in history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]


@pytest.mark.asyncio
async def test_sandbox_reservation_service_invalidates_allocation_reservation() -> None:
    repository = ReservationOnlyRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = SandboxControlPlaneReservationService(publication=publication)

    await service.publish_allocation_reservation(
        sandbox_id="sb-2",
        run_id="run-2",
        compose_project="orket-sandbox-run-2",
        ports=PortAllocation(api=8002, frontend=3002, database=5434, admin_tool=8082),
        creation_timestamp="2026-03-24T00:00:00+00:00",
        instance_id="runner-a",
    )
    invalidated = await service.invalidate_allocation_reservation(
        sandbox_id="sb-2",
        instance_id="runner-a",
        invalidation_basis="sandbox_create_record_failed",
    )

    assert invalidated.status is ReservationStatus.INVALIDATED
