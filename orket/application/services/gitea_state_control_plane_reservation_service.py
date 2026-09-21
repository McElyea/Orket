from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_lease_service import (
    GiteaStateControlPlaneLeaseService,
)
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts import ReservationRecord
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus
from orket.runtime_paths import resolve_control_plane_db_path

LOGGER = logging.getLogger(__name__)


class GiteaStateControlPlaneReservationService:
    """Publishes Gitea worker claim reservations and promotion into lease authority."""

    PROMOTION_RULE = "promote_after_claim_transition"

    def __init__(self, *, publication: ControlPlanePublicationService, now_utc: Callable[[], str] | None = None) -> None:
        self.publication = publication
        self.now_utc = RuntimeInputService().utc_now_iso if now_utc is None else now_utc

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
        timestamp = str(observed_at or self.now_utc()).strip()
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
        timestamp = str(observed_at or self.now_utc()).strip()
        try:
            return await self.publication.promote_reservation_to_lease(
                reservation_id=self.reservation_id_for(card_id, lease_epoch),
                promoted_lease_id=GiteaStateControlPlaneLeaseService.lease_id_for(card_id),
                supervisor_authority_ref=f"gitea-state-worker:claim-transition:{str(card_id).strip()}:promote",
                promotion_basis=(
                    "gitea_state_worker_claim_transition_succeeded"
                    f";publication_timestamp={timestamp}"
                ),
            )
        except (OSError, ValueError, RuntimeError, TypeError, sqlite3.Error):
            LOGGER.exception("Gitea reservation promotion failed", extra={"card_id": card_id, "lease_epoch": lease_epoch})
            await self._rollback_failed_promotion(
                card_id=card_id,
                lease_epoch=lease_epoch,
                observed_at=timestamp,
            )
            raise

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

    async def _rollback_failed_promotion(
        self,
        *,
        card_id: str,
        lease_epoch: int,
        observed_at: str,
    ) -> None:
        lease = await self.publication.repository.get_latest_lease_record(
            lease_id=GiteaStateControlPlaneLeaseService.lease_id_for(card_id)
        )
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            released_lease = await self.publication.publish_lease(
                lease_id=lease.lease_id,
                resource_id=lease.resource_id,
                holder_ref=lease.holder_ref,
                lease_epoch=lease.lease_epoch,
                publication_timestamp=observed_at,
                expiry_basis=(
                    "gitea_state_worker_claim_promotion_failed"
                    f";lease_epoch={int(lease_epoch):08d}"
                ),
                status=LeaseStatus.RELEASED,
                granted_timestamp=lease.granted_timestamp,
                last_confirmed_observation=lease.last_confirmed_observation,
                cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
                source_reservation_id=lease.source_reservation_id,
            )
            await GiteaStateControlPlaneLeaseService(publication=self.publication, now_utc=self.now_utc).publish_resource_snapshot(
                card_id=card_id,
                lease=released_lease,
            )
        reservation_id = self.reservation_id_for(card_id, lease_epoch)
        reservation = await self.publication.repository.get_latest_reservation_record(
            reservation_id=reservation_id
        )
        if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
            await self.publication.invalidate_reservation(
                reservation_id=reservation.reservation_id,
                supervisor_authority_ref=(
                    f"gitea-state-worker:claim-transition:{str(card_id).strip()}:promote_fail_closeout"
                ),
                invalidation_basis=(
                    "gitea_state_worker_claim_promotion_failed"
                    f";lease_epoch={int(lease_epoch):08d}"
                ),
            )


def build_gitea_state_control_plane_reservation_service(
    db_path: str | Path | None = None,
    *, now_utc: Callable[[], str] | None = None,
) -> GiteaStateControlPlaneReservationService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneReservationService(publication=publication, now_utc=now_utc)


__all__ = [
    "GiteaStateControlPlaneReservationService",
    "build_gitea_state_control_plane_reservation_service",
]
