from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.core.contracts import LeaseRecord
from orket.core.domain import (
    CleanupAuthorityClass,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
)
from orket.core.domain.coordinator_card import Card
from orket.runtime_paths import resolve_control_plane_db_path


class CoordinatorControlPlaneAuthorityError(ValueError):
    """Raised when coordinator lease/resource authority has drifted."""


class CoordinatorControlPlaneLeaseService:
    """Publishes truthful lease history for standalone coordinator cards."""

    CLEANUP_ELIGIBILITY_RULE = "coordinator_complete_or_fail"

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def lease_id_for(card_id: str) -> str:
        return f"coordinator-lease:{str(card_id).strip()}"

    @staticmethod
    def resource_id_for(card_id: str) -> str:
        return f"coordinator-card:{str(card_id).strip()}"

    @staticmethod
    def holder_ref_for(node_id: str) -> str:
        return f"coordinator-node:{str(node_id).strip()}"

    async def publish_claim(
        self,
        *,
        card: Card,
        node_id: str,
        lease_duration: float,
        observed_at: str | None = None,
        lease_epoch: int | None = None,
        source_reservation_id: str | None = None,
    ) -> LeaseRecord | None:
        if not self._should_publish(card=card, node_id=node_id):
            return None
        epoch = lease_epoch if lease_epoch is not None else await self.next_claim_epoch(card_id=card.id, node_id=node_id)
        timestamp = observed_at or self._utc_now()
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card.id),
            resource_id=self.resource_id_for(card.id),
            holder_ref=self.holder_ref_for(node_id),
            lease_epoch=epoch,
            publication_timestamp=timestamp,
            expiry_basis=self._active_expiry_basis(card=card, lease_duration=lease_duration),
            status=LeaseStatus.ACTIVE,
            granted_timestamp=timestamp,
            last_confirmed_observation=self._observation_ref(card=card, node_id=node_id, event="claim"),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
            source_reservation_id=None if source_reservation_id is None else str(source_reservation_id).strip(),
        )
        await self.publish_resource_snapshot(card_id=card.id, lease=lease)
        return lease

    async def next_claim_epoch(self, *, card_id: str, node_id: str) -> int:
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self.lease_id_for(card_id))
        return self._next_epoch(latest=latest, holder_ref=self.holder_ref_for(node_id))

    async def publish_renew(
        self,
        *,
        card: Card,
        node_id: str,
        lease_duration: float,
        observed_at: str | None = None,
    ) -> LeaseRecord | None:
        if not self._should_publish(card=card, node_id=node_id):
            return None
        latest = await self._get_active_lease_authority(
            card_id=card.id,
            error_context="coordinator renew",
            allow_missing=True,
        )
        if latest is None:
            return None
        timestamp = observed_at or self._utc_now()
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card.id),
            resource_id=self.resource_id_for(card.id),
            holder_ref=self.holder_ref_for(node_id),
            lease_epoch=latest.lease_epoch,
            publication_timestamp=timestamp,
            expiry_basis=self._active_expiry_basis(card=card, lease_duration=lease_duration),
            status=LeaseStatus.ACTIVE,
            granted_timestamp=latest.granted_timestamp,
            last_confirmed_observation=self._observation_ref(card=card, node_id=node_id, event="renew"),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card.id, lease=lease)
        return lease

    async def publish_expired_from_snapshot(
        self,
        *,
        card: Card,
        observed_at: str | None = None,
    ) -> LeaseRecord | None:
        if card.hedged_execution or not str(card.claimed_by or "").strip():
            return None
        if card.lease_expires_at is None or card.lease_expires_at > time.monotonic():
            return None
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self.lease_id_for(card.id))
        if latest is None or latest.status is LeaseStatus.EXPIRED:
            return latest
        if latest.status is not LeaseStatus.ACTIVE:
            raise CoordinatorControlPlaneAuthorityError(
                f"coordinator expiry expected active lease authority: {self.lease_id_for(card.id)}"
            )
        await self._require_resource_authority(
            card_id=card.id,
            lease=latest,
            error_context="coordinator expiry",
        )
        timestamp = observed_at or self._utc_now()
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card.id),
            resource_id=self.resource_id_for(card.id),
            holder_ref=self.holder_ref_for(str(card.claimed_by)),
            lease_epoch=latest.lease_epoch,
            publication_timestamp=timestamp,
            expiry_basis=self._expired_expiry_basis(card=card),
            status=LeaseStatus.EXPIRED,
            granted_timestamp=latest.granted_timestamp,
            last_confirmed_observation=self._observation_ref(card=card, node_id=str(card.claimed_by), event="expire"),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card.id, lease=lease)
        return lease

    async def publish_release(
        self,
        *,
        card_id: str,
        node_id: str,
        final_state: str,
        observed_at: str | None = None,
    ) -> LeaseRecord | None:
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self.lease_id_for(card_id))
        if latest is None:
            return None
        if latest.status is LeaseStatus.RELEASED:
            return latest
        if latest.status is not LeaseStatus.ACTIVE:
            raise CoordinatorControlPlaneAuthorityError(
                f"coordinator {str(final_state).strip().lower() or 'unknown'} closeout expected active lease authority: "
                f"{self.lease_id_for(card_id)}"
            )
        await self._require_resource_authority(
            card_id=card_id,
            lease=latest,
            error_context=f"coordinator {str(final_state).strip().lower() or 'unknown'} closeout",
        )
        timestamp = observed_at or self._utc_now()
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(node_id),
            lease_epoch=latest.lease_epoch,
            publication_timestamp=timestamp,
            expiry_basis=f"coordinator_{str(final_state).strip().lower() or 'unknown'}",
            status=LeaseStatus.RELEASED,
            granted_timestamp=latest.granted_timestamp,
            last_confirmed_observation=f"coordinator-card:{str(card_id).strip()}:{str(final_state).strip().lower()}",
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    async def require_active_authority(self, *, card_id: str, error_context: str) -> LeaseRecord:
        lease = await self._get_active_lease_authority(card_id=card_id, error_context=error_context)
        if lease is None:
            raise CoordinatorControlPlaneAuthorityError(
                f"{error_context} missing active lease authority: {self.lease_id_for(card_id)}"
            )
        return lease

    async def publish_resource_snapshot(self, *, card_id: str, lease: LeaseRecord) -> None:
        event = self._resource_event_for_status(lease.status)
        await self._publish_resource_snapshot(
            resource_id=self.resource_id_for(card_id),
            namespace_scope=self.resource_id_for(card_id),
            publication_timestamp=lease.publication_timestamp,
            current_observed_state=f"lease_status:{lease.status.value};observation:{lease.last_confirmed_observation}",
            provenance_ref=lease.last_confirmed_observation or f"coordinator-card:{card_id}:{event}",
        )

    @staticmethod
    def _should_publish(*, card: Card, node_id: str) -> bool:
        normalized_node = str(node_id).strip()
        return not card.hedged_execution and str(card.claimed_by or "").strip() == normalized_node

    @staticmethod
    def _next_epoch(*, latest: LeaseRecord | None, holder_ref: str) -> int:
        if latest is None:
            return 1
        if latest.status is not LeaseStatus.ACTIVE:
            return latest.lease_epoch + 1
        if latest.holder_ref != holder_ref:
            return latest.lease_epoch + 1
        return latest.lease_epoch

    @staticmethod
    def _active_expiry_basis(*, card: Card, lease_duration: float) -> str:
        expires_at = "none" if card.lease_expires_at is None else f"{float(card.lease_expires_at):.6f}"
        return (
            "coordinator_store_lease"
            f";lease_duration={float(lease_duration):.6f}"
            f";lease_expires_at_monotonic={expires_at}"
        )

    @staticmethod
    def _expired_expiry_basis(*, card: Card) -> str:
        expires_at = "none" if card.lease_expires_at is None else f"{float(card.lease_expires_at):.6f}"
        return f"coordinator_store_expired;lease_expires_at_monotonic={expires_at}"

    @staticmethod
    def _observation_ref(*, card: Card, node_id: str, event: str) -> str:
        return (
            f"coordinator-card:{str(card.id).strip()}"
            f":attempts:{int(card.attempts)}"
            f":node:{str(node_id).strip()}"
            f":event:{str(event).strip()}"
        )

    async def _publish_resource_snapshot(
        self,
        *,
        resource_id: str,
        namespace_scope: str,
        publication_timestamp: str,
        current_observed_state: str,
        provenance_ref: str,
    ) -> None:
        await self.publication.publish_resource(
            resource_id=resource_id,
            resource_kind="coordinator_card",
            namespace_scope=namespace_scope,
            ownership_class=OwnershipClass.SHARED_GOVERNED,
            current_observed_state=current_observed_state,
            last_observed_timestamp=publication_timestamp,
            cleanup_authority_class=CleanupAuthorityClass.CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION,
            provenance_ref=provenance_ref,
            reconciliation_status="external_store_authoritative",
            orphan_classification=OrphanClassification.NOT_ORPHANED,
        )

    async def _get_active_lease_authority(
        self,
        *,
        card_id: str,
        error_context: str,
        allow_missing: bool = False,
    ) -> LeaseRecord | None:
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self.lease_id_for(card_id))
        if latest is None:
            if allow_missing:
                return None
            raise CoordinatorControlPlaneAuthorityError(
                f"{error_context} missing lease authority: {self.lease_id_for(card_id)}"
            )
        if latest.status is not LeaseStatus.ACTIVE:
            raise CoordinatorControlPlaneAuthorityError(
                f"{error_context} expected active lease authority: {self.lease_id_for(card_id)}"
            )
        await self._require_resource_authority(card_id=card_id, lease=latest, error_context=error_context)
        return latest

    async def _require_resource_authority(
        self,
        *,
        card_id: str,
        lease: LeaseRecord,
        error_context: str,
    ) -> None:
        expected_resource_id = self.resource_id_for(card_id)
        if str(lease.resource_id or "").strip() != expected_resource_id:
            raise CoordinatorControlPlaneAuthorityError(
                f"{error_context} lease resource id drift: {lease.resource_id!r} != {expected_resource_id!r}"
            )
        resource = await self.publication.repository.get_latest_resource_record(resource_id=expected_resource_id)
        require_resource_snapshot_matches_lease(
            resource=resource,
            lease=lease,
            expected_resource_kind="coordinator_card",
            expected_namespace_scope=expected_resource_id,
            error_context=error_context,
            error_factory=CoordinatorControlPlaneAuthorityError,
        )

    @staticmethod
    def _resource_event_for_status(status: LeaseStatus) -> str:
        if status is LeaseStatus.ACTIVE:
            return "claim"
        if status is LeaseStatus.EXPIRED:
            return "expire"
        if status is LeaseStatus.RELEASED:
            return "released"
        return str(status.value)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()


def build_coordinator_control_plane_lease_service(
    db_path: str | Path | None = None,
) -> CoordinatorControlPlaneLeaseService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return CoordinatorControlPlaneLeaseService(publication=publication)


__all__ = [
    "CoordinatorControlPlaneAuthorityError",
    "CoordinatorControlPlaneLeaseService",
    "build_coordinator_control_plane_lease_service",
]
