from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_lease_service import (
    GiteaStateControlPlaneLeaseService,
)
from orket.core.contracts import ReservationRecord
from orket.core.domain import ReservationKind, ReservationStatus
from orket.runtime_paths import resolve_control_plane_db_path


class GiteaStateControlPlaneReservationService:
    """Publishes Gitea worker claim reservations and promotion into lease authority."""

    PROMOTION_RULE = "promote_after_claim_transition"

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def reservation_id_for(card_id: str, lease_epoch: int) -> str:
        normalized_card_id = str(card_id).strip()
        if not normalized_card_id:
            raise ValueError("card_id is required")
        if int(lease_epoch) <= 0:
            raise ValueError("lease_epoch must be >= 1")
        return f"gitea-claim-reservation:{normalized_card_id}:lease_epoch:{int(lease_epoch):08d}"

    async def publish_claim_reservation(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_epoch: int,
        observed_at: str | None = None,
    ) -> ReservationRecord:
        timestamp = str(observed_at or self._utc_now()).strip()
        return await self.publication.publish_reservation(
            reservation_id=self.reservation_id_for(card_id, lease_epoch),
            holder_ref=GiteaStateControlPlaneLeaseService.holder_ref_for(worker_id),
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref=GiteaStateControlPlaneLeaseService.resource_id_for(card_id),
            creation_timestamp=timestamp,
            expiry_or_invalidation_basis=f"gitea_state_worker_claim_reserved;lease_epoch={int(lease_epoch):08d}",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"gitea-state-worker:{str(worker_id).strip()}:claim:{str(card_id).strip()}",
            promotion_rule=self.PROMOTION_RULE,
        )

    async def promote_claim_reservation(
        self,
        *,
        card_id: str,
        lease_epoch: int,
        observed_at: str | None = None,
    ) -> ReservationRecord:
        return await self.publication.promote_reservation_to_lease(
            reservation_id=self.reservation_id_for(card_id, lease_epoch),
            promoted_lease_id=GiteaStateControlPlaneLeaseService.lease_id_for(card_id),
            supervisor_authority_ref=f"gitea-state-worker:claim-transition:{str(card_id).strip()}:promote",
            promotion_basis=(
                "gitea_state_worker_claim_transition_succeeded"
                f";publication_timestamp={str(observed_at or self._utc_now()).strip()}"
            ),
        )

    async def invalidate_claim_reservation(
        self,
        *,
        card_id: str,
        lease_epoch: int,
        reason: str,
    ) -> ReservationRecord:
        return await self.publication.invalidate_reservation(
            reservation_id=self.reservation_id_for(card_id, lease_epoch),
            supervisor_authority_ref=f"gitea-state-worker:claim-transition:{str(card_id).strip()}:invalidate",
            invalidation_basis=f"gitea_state_worker_claim_transition_failed:{str(reason or 'unknown').strip()}",
        )

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()


def build_gitea_state_control_plane_reservation_service(
    db_path: str | Path | None = None,
) -> GiteaStateControlPlaneReservationService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneReservationService(publication=publication)


__all__ = [
    "GiteaStateControlPlaneReservationService",
    "build_gitea_state_control_plane_reservation_service",
]
