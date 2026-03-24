# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_reservation_service import (
    CoordinatorControlPlaneReservationService,
)
from orket.core.domain import ReservationKind, ReservationStatus
from orket.core.domain.coordinator_card import Card
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


def _card(*, hedged_execution: bool = False) -> Card:
    return Card(
        id="card-1",
        payload={"task": "demo"},
        state="CLAIMED",
        claimed_by="worker-a",
        lease_expires_at=42.0,
        result=None,
        attempts=1,
        hedged_execution=hedged_execution,
    )


@pytest.mark.asyncio
async def test_coordinator_reservation_service_publishes_and_promotes_claim_reservation() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = CoordinatorControlPlaneReservationService(publication=publication)

    reservation = await service.publish_claim_reservation(
        card=_card(),
        node_id="worker-a",
        lease_epoch=1,
        observed_at="2026-03-24T10:00:00+00:00",
    )
    promoted = await service.promote_claim_reservation(
        card_id="card-1",
        lease_epoch=1,
        observed_at="2026-03-24T10:00:00+00:00",
    )

    assert reservation is not None
    assert reservation.reservation_kind is ReservationKind.RESOURCE
    assert reservation.status is ReservationStatus.ACTIVE
    assert promoted.status is ReservationStatus.PROMOTED_TO_LEASE
    assert promoted.promoted_lease_id == "coordinator-lease:card-1"


@pytest.mark.asyncio
async def test_coordinator_reservation_service_skips_hedged_claims() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = CoordinatorControlPlaneReservationService(publication=publication)

    reservation = await service.publish_claim_reservation(
        card=_card(hedged_execution=True),
        node_id="worker-a",
        lease_epoch=1,
        observed_at="2026-03-24T10:01:00+00:00",
    )

    assert reservation is None
