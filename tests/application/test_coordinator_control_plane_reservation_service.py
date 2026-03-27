# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_lease_service import (
    CoordinatorControlPlaneLeaseService,
)
from orket.application.services.coordinator_control_plane_reservation_service import (
    CoordinatorControlPlaneReservationService,
)
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus
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


@pytest.mark.asyncio
async def test_coordinator_reservation_service_fail_closes_active_authority_on_promotion_failure() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    reservation_service = CoordinatorControlPlaneReservationService(publication=publication)
    lease_service = CoordinatorControlPlaneLeaseService(publication=publication)
    card = _card()

    reservation = await reservation_service.publish_claim_reservation(
        card=card,
        node_id="worker-a",
        lease_epoch=1,
        observed_at="2026-03-24T10:05:00+00:00",
    )
    assert reservation is not None
    await lease_service.publish_claim(
        card=card,
        node_id="worker-a",
        lease_duration=30.0,
        observed_at="2026-03-24T10:05:00+00:00",
        lease_epoch=1,
        source_reservation_id=reservation.reservation_id,
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await reservation_service.promote_claim_reservation(
            card_id="card-1",
            lease_epoch=1,
            observed_at="2026-03-24T10:05:01+00:00",
        )

    latest_reservation = await repository.get_latest_reservation_record(
        reservation_id=CoordinatorControlPlaneReservationService.reservation_id_for("card-1", 1)
    )
    latest_lease = await repository.get_latest_lease_record(
        lease_id=CoordinatorControlPlaneLeaseService.lease_id_for("card-1")
    )

    assert latest_reservation is not None
    assert latest_reservation.status is ReservationStatus.INVALIDATED
    assert latest_lease is not None
    assert latest_lease.status is LeaseStatus.RELEASED
