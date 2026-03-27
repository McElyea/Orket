# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_lease_service import (
    GiteaStateControlPlaneLeaseService,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
)
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus
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


@pytest.mark.asyncio
async def test_gitea_reservation_service_fail_closes_active_authority_on_promotion_failure() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    reservation_service = GiteaStateControlPlaneReservationService(publication=publication)
    lease_service = GiteaStateControlPlaneLeaseService(publication=publication)

    reservation = await reservation_service.publish_claim_reservation(
        card_id="9",
        worker_id="worker-z",
        lease_epoch=5,
        observed_at="2026-03-24T12:05:00+00:00",
    )
    await lease_service.publish_claimed_lease(
        card_id="9",
        worker_id="worker-z",
        lease_observation={
            "version": 9,
            "lease": {
                "epoch": 5,
                "acquired_at": "2026-03-24T12:05:00+00:00",
                "expires_at": "2026-03-24T12:06:00+00:00",
            },
        },
        lease_seconds=30,
        source_reservation_id=reservation.reservation_id,
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await reservation_service.promote_claim_reservation(
            card_id="9",
            lease_epoch=5,
            observed_at="2026-03-24T12:05:01+00:00",
        )

    latest_reservation = await repository.get_latest_reservation_record(
        reservation_id=GiteaStateControlPlaneReservationService.reservation_id_for("9", 5)
    )
    latest_lease = await repository.get_latest_lease_record(
        lease_id=GiteaStateControlPlaneLeaseService.lease_id_for("9")
    )

    assert latest_reservation is not None
    assert latest_reservation.status is ReservationStatus.INVALIDATED
    assert latest_lease is not None
    assert latest_lease.status is LeaseStatus.RELEASED
