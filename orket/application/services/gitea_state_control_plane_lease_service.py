from __future__ import annotations

from collections.abc import Mapping
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
from orket.runtime_paths import resolve_control_plane_db_path


class GiteaStateControlPlaneAuthorityError(ValueError):
    """Raised when Gitea worker lease/resource authority has drifted."""


class GiteaStateControlPlaneLeaseService:
    """Publishes non-sandbox Gitea worker lease truth into the control-plane store."""

    CLEANUP_ELIGIBILITY_RULE = "gitea_state_worker_release_or_fail"

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def lease_id_for(card_id: str) -> str:
        return f"gitea-card-lease:{str(card_id).strip()}"

    @staticmethod
    def resource_id_for(card_id: str) -> str:
        return f"gitea-card:{str(card_id).strip()}"

    @staticmethod
    def holder_ref_for(worker_id: str) -> str:
        return f"gitea-worker:{str(worker_id).strip()}"

    async def publish_claimed_lease(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_observation: Mapping[str, object],
        lease_seconds: int,
        source_reservation_id: str | None = None,
    ) -> LeaseRecord:
        publication_timestamp = self._utc_now()
        lease_payload = self._lease_payload(lease_observation)
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(worker_id),
            lease_epoch=self._lease_epoch(lease_observation),
            publication_timestamp=publication_timestamp,
            expiry_basis=self._active_expiry_basis(
                lease_observation=lease_observation,
                lease_payload=lease_payload,
                lease_seconds=lease_seconds,
            ),
            status=LeaseStatus.ACTIVE,
            granted_timestamp=str(lease_payload.get("acquired_at") or publication_timestamp),
            last_confirmed_observation=self._observation_ref(card_id=card_id, lease_observation=lease_observation),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
            source_reservation_id=None if source_reservation_id is None else str(source_reservation_id).strip(),
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    async def publish_renewed_lease(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_observation: Mapping[str, object],
        lease_seconds: int,
    ) -> LeaseRecord:
        latest = await self.require_active_authority(
            card_id=card_id,
            error_context="gitea worker renew publication",
        )
        publication_timestamp = self._utc_now()
        lease_payload = self._lease_payload(lease_observation)
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(worker_id),
            lease_epoch=self._lease_epoch(lease_observation),
            publication_timestamp=publication_timestamp,
            expiry_basis=self._active_expiry_basis(
                lease_observation=lease_observation,
                lease_payload=lease_payload,
                lease_seconds=lease_seconds,
            ),
            status=LeaseStatus.ACTIVE,
            granted_timestamp=latest.granted_timestamp,
            last_confirmed_observation=self._observation_ref(card_id=card_id, lease_observation=lease_observation),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    async def publish_expired_lease(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_observation: Mapping[str, object],
        reason: str,
    ) -> LeaseRecord:
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(worker_id),
            lease_epoch=self._lease_epoch(lease_observation),
            publication_timestamp=self._utc_now(),
            expiry_basis=f"gitea_state_worker_detected_expiry:{str(reason or 'E_LEASE_EXPIRED').strip()}",
            status=LeaseStatus.EXPIRED,
            granted_timestamp=str(self._lease_payload(lease_observation).get("acquired_at") or self._utc_now()),
            last_confirmed_observation=self._observation_ref(card_id=card_id, lease_observation=lease_observation),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    async def publish_uncertain_lease(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_observation: Mapping[str, object],
        reason: str,
    ) -> LeaseRecord:
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(worker_id),
            lease_epoch=self._lease_epoch(lease_observation),
            publication_timestamp=self._utc_now(),
            expiry_basis=f"gitea_state_worker_claim_failure:{str(reason or 'unknown').strip()}",
            status=LeaseStatus.UNCERTAIN,
            granted_timestamp=str(self._lease_payload(lease_observation).get("acquired_at") or self._utc_now()),
            last_confirmed_observation=self._observation_ref(card_id=card_id, lease_observation=lease_observation),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    async def publish_released_lease(
        self,
        *,
        card_id: str,
        worker_id: str,
        lease_observation: Mapping[str, object],
        final_state: str,
    ) -> LeaseRecord:
        lease = await self.publication.publish_lease(
            lease_id=self.lease_id_for(card_id),
            resource_id=self.resource_id_for(card_id),
            holder_ref=self.holder_ref_for(worker_id),
            lease_epoch=self._lease_epoch(lease_observation),
            publication_timestamp=self._utc_now(),
            expiry_basis=f"gitea_state_worker_release_or_fail:{str(final_state or 'unknown').strip()}",
            status=LeaseStatus.RELEASED,
            granted_timestamp=str(self._lease_payload(lease_observation).get("acquired_at") or self._utc_now()),
            last_confirmed_observation=self._observation_ref(card_id=card_id, lease_observation=lease_observation),
            cleanup_eligibility_rule=self.CLEANUP_ELIGIBILITY_RULE,
        )
        await self.publish_resource_snapshot(card_id=card_id, lease=lease)
        return lease

    @staticmethod
    def _lease_payload(lease_observation: Mapping[str, object]) -> Mapping[str, object]:
        nested = lease_observation.get("lease")
        if isinstance(nested, Mapping):
            return nested
        return lease_observation

    @classmethod
    def _lease_epoch(cls, lease_observation: Mapping[str, object]) -> int:
        payload = cls._lease_payload(lease_observation)
        raw = payload.get("epoch")
        if raw is None:
            raw = lease_observation.get("lease_epoch")
        try:
            return cls._required_int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("gitea control-plane lease publication requires lease epoch") from exc

    @classmethod
    def _observation_ref(cls, *, card_id: str, lease_observation: Mapping[str, object]) -> str:
        version = lease_observation.get("version")
        if version is not None:
            return f"gitea-card-snapshot:{str(card_id).strip()}:version:{cls._required_int(version)}"
        return f"gitea-card-lease-observation:{str(card_id).strip()}:epoch:{cls._lease_epoch(lease_observation):08d}"

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, (str, bytes, bytearray, int, float)):
            raise TypeError("expected integer-like value")
        return int(value)

    @staticmethod
    def _active_expiry_basis(
        *,
        lease_observation: Mapping[str, object],
        lease_payload: Mapping[str, object],
        lease_seconds: int,
    ) -> str:
        expires_at = str(lease_payload.get("expires_at") or "").strip() or "unknown"
        version = str(lease_observation.get("version") or "").strip() or "unknown"
        return (
            "gitea_state_backend_lease"
            f";lease_seconds={max(1, int(lease_seconds))}"
            f";expires_at={expires_at}"
            f";snapshot_version={version}"
        )

    async def publish_resource_snapshot(self, *, card_id: str, lease: LeaseRecord) -> None:
        await self.publication.publish_resource(
            resource_id=self.resource_id_for(card_id),
            resource_kind="gitea_card",
            namespace_scope=self.namespace_scope_for(card_id),
            ownership_class=OwnershipClass.SHARED_GOVERNED,
            current_observed_state=f"lease_status:{lease.status.value};observation:{lease.last_confirmed_observation}",
            last_observed_timestamp=lease.publication_timestamp,
            cleanup_authority_class=CleanupAuthorityClass.CLEANUP_FORBIDDEN_WITHOUT_EXTERNAL_CONFIRMATION,
            provenance_ref=lease.last_confirmed_observation or f"gitea-card:{str(card_id).strip()}",
            reconciliation_status="external_state_authoritative",
            orphan_classification=(
                OrphanClassification.OWNERSHIP_CONFLICT
                if lease.status is LeaseStatus.UNCERTAIN
                else OrphanClassification.NOT_ORPHANED
            ),
        )

    async def require_active_authority(self, *, card_id: str, error_context: str) -> LeaseRecord:
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self.lease_id_for(card_id))
        if latest is None:
            raise GiteaStateControlPlaneAuthorityError(
                f"{error_context} missing lease authority: {self.lease_id_for(card_id)}"
            )
        if latest.status is not LeaseStatus.ACTIVE:
            raise GiteaStateControlPlaneAuthorityError(
                f"{error_context} expected active lease authority: {self.lease_id_for(card_id)}"
            )
        expected_resource_id = self.resource_id_for(card_id)
        if str(latest.resource_id or "").strip() != expected_resource_id:
            raise GiteaStateControlPlaneAuthorityError(
                f"{error_context} lease resource id drift: {latest.resource_id!r} != {expected_resource_id!r}"
            )
        resource = await self.publication.repository.get_latest_resource_record(resource_id=expected_resource_id)
        require_resource_snapshot_matches_lease(
            resource=resource,
            lease=latest,
            expected_resource_kind="gitea_card",
            expected_namespace_scope=self.namespace_scope_for(card_id),
            error_context=error_context,
            error_factory=GiteaStateControlPlaneAuthorityError,
        )
        return latest

    @staticmethod
    def namespace_scope_for(card_id: str) -> str:
        return f"issue:{str(card_id).strip()}"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()


def build_gitea_state_control_plane_lease_service(
    db_path: str | Path | None = None,
) -> GiteaStateControlPlaneLeaseService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneLeaseService(publication=publication)


__all__ = [
    "GiteaStateControlPlaneAuthorityError",
    "GiteaStateControlPlaneLeaseService",
    "build_gitea_state_control_plane_lease_service",
]
