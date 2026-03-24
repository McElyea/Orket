# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
)
from orket.core.domain import ReservationKind, ReservationStatus
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_gitea_reservation_service_publishes_and_promotes_claim_reservation() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = GiteaStateControlPlaneReservationService(publication=publication)

    reservation = await service.publish_claim_reservation(
        card_id="7",
        worker_id="worker-a",
        lease_epoch=3,
        observed_at="2026-03-24T12:00:00+00:00",
    )
    promoted = await service.promote_claim_reservation(
        card_id="7",
        lease_epoch=3,
        observed_at="2026-03-24T12:00:01+00:00",
    )

    assert reservation.reservation_kind is ReservationKind.RESOURCE
    assert reservation.status is ReservationStatus.ACTIVE
    assert promoted.status is ReservationStatus.PROMOTED_TO_LEASE
    assert promoted.promoted_lease_id == "gitea-card-lease:7"


@pytest.mark.asyncio
async def test_gitea_reservation_service_invalidates_claim_reservation() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = GiteaStateControlPlaneReservationService(publication=publication)

    await service.publish_claim_reservation(
        card_id="8",
        worker_id="worker-b",
        lease_epoch=4,
        observed_at="2026-03-24T12:01:00+00:00",
    )
    invalidated = await service.invalidate_claim_reservation(
        card_id="8",
        lease_epoch=4,
        reason="Stale transition rejected",
    )

    assert invalidated.status is ReservationStatus.INVALIDATED
