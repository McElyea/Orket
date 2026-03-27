from __future__ import annotations

from datetime import UTC, datetime

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_lease_service import (
    CoordinatorControlPlaneLeaseService,
)
from orket.core.contracts import ReservationRecord
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus
from orket.core.domain.coordinator_card import Card


class CoordinatorControlPlaneReservationService:
    """Publishes non-hedged coordinator claim reservations and promotion to lease."""

    PROMOTION_RULE = "promote_on_non_hedged_claim_confirmation"

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def reservation_id_for(card_id: str, lease_epoch: int) -> str:
        normalized_id = str(card_id).strip()
        if not normalized_id:
            raise ValueError("card_id is required")
        if int(lease_epoch) <= 0:
            raise ValueError("lease_epoch must be >= 1")
        return f"coordinator-reservation:{normalized_id}:lease_epoch:{int(lease_epoch):08d}"

    async def publish_claim_reservation(
        self,
        *,
        card: Card,
        node_id: str,
        lease_epoch: int,
        observed_at: str | None = None,
    ) -> ReservationRecord | None:
        if not self._should_publish(card=card, node_id=node_id):
            return None
        timestamp = observed_at or self._utc_now()
        return await self.publication.publish_reservation(
            reservation_id=self.reservation_id_for(card.id, lease_epoch),
            holder_ref=CoordinatorControlPlaneLeaseService.holder_ref_for(node_id),
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref=CoordinatorControlPlaneLeaseService.resource_id_for(card.id),
            creation_timestamp=timestamp,
            expiry_or_invalidation_basis=self._reservation_basis(card=card),
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"coordinator-api:claim:{str(card.id).strip()}:reserve",
            promotion_rule=self.PROMOTION_RULE,
        )

    async def promote_claim_reservation(
        self,
        *,
        card_id: str,
        lease_epoch: int,
        observed_at: str | None = None,
    ) -> ReservationRecord:
        timestamp = str(observed_at or self._utc_now()).strip()
        try:
            return await self.publication.promote_reservation_to_lease(
                reservation_id=self.reservation_id_for(card_id, lease_epoch),
                promoted_lease_id=CoordinatorControlPlaneLeaseService.lease_id_for(card_id),
                supervisor_authority_ref=f"coordinator-api:claim:{str(card_id).strip()}:promote",
                promotion_basis=(
                    "coordinator_claim_promoted_to_lease"
                    f";publication_timestamp={timestamp}"
                ),
            )
        except Exception:
            await self._rollback_failed_promotion(
                card_id=card_id,
                lease_epoch=lease_epoch,
                observed_at=timestamp,
            )
            raise

    @staticmethod
    def _should_publish(*, card: Card, node_id: str) -> bool:
        normalized_node = str(node_id).strip()
        return not card.hedged_execution and str(card.claimed_by or "").strip() == normalized_node

    @staticmethod
    def _reservation_basis(*, card: Card) -> str:
        expires_at = "none" if card.lease_expires_at is None else f"{float(card.lease_expires_at):.6f}"
        return (
            "coordinator_claim_reserved"
            f";card={str(card.id).strip()}"
            f";attempts={int(card.attempts)}"
            f";lease_expires_at_monotonic={expires_at}"
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

    async def _rollback_failed_promotion(
        self,
        *,
        card_id: str,
        lease_epoch: int,
        observed_at: str,
    ) -> None:
        lease = await self.publication.repository.get_latest_lease_record(
            lease_id=CoordinatorControlPlaneLeaseService.lease_id_for(card_id)
        )
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            rollback_timestamp = (
                observed_at
                if observed_at >= lease.publication_timestamp
                else lease.publication_timestamp
            )
            released_lease = await self.publication.publish_lease(
                lease_id=lease.lease_id,
                resource_id=lease.resource_id,
                holder_ref=lease.holder_ref,
                lease_epoch=lease.lease_epoch,
                publication_timestamp=rollback_timestamp,
                expiry_basis=(
                    "coordinator_claim_promotion_failed"
                    f";lease_epoch={int(lease_epoch):08d}"
                ),
                status=LeaseStatus.RELEASED,
                granted_timestamp=lease.granted_timestamp,
                last_confirmed_observation=lease.last_confirmed_observation,
                cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
                source_reservation_id=lease.source_reservation_id,
            )
            await CoordinatorControlPlaneLeaseService(
                publication=self.publication
            ).publish_resource_snapshot(card_id=card_id, lease=released_lease)
        reservation_id = self.reservation_id_for(card_id, lease_epoch)
        reservation = await self.publication.repository.get_latest_reservation_record(
            reservation_id=reservation_id
        )
        if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
            await self.publication.invalidate_reservation(
                reservation_id=reservation.reservation_id,
                supervisor_authority_ref=(
                    f"coordinator-api:claim:{str(card_id).strip()}:promote_fail_closeout"
                ),
                invalidation_basis=(
                    "coordinator_claim_promotion_failed"
                    f";lease_epoch={int(lease_epoch):08d}"
                ),
            )


__all__ = ["CoordinatorControlPlaneReservationService"]
