from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import LeaseRecord
from orket.core.domain import LeaseStatus
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


class SandboxControlPlaneLeaseError(ValueError):
    """Raised when sandbox lifecycle state cannot truthfully publish lease authority."""


class SandboxControlPlaneLeaseService:
    """Publishes first-class lease truth for sandbox lifecycle authority."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_from_record(
        self,
        *,
        record: SandboxLifecycleRecord,
        publication_timestamp: str,
    ) -> LeaseRecord:
        owner = str(record.owner_instance_id or "").strip()
        status = self._status_for_record(record)
        if record.run_id is None:
            raise SandboxControlPlaneLeaseError("sandbox lease publication requires run_id")
        if not owner:
            raise SandboxControlPlaneLeaseError("sandbox lease publication requires owner_instance_id")
        latest = await self.publication.repository.get_latest_lease_record(lease_id=self._lease_id(record))
        if (
            latest is not None
            and latest.lease_epoch == record.lease_epoch
            and latest.status is status
            and latest.publication_timestamp == publication_timestamp
        ):
            return latest
        return await self.publication.publish_lease(
            lease_id=self._lease_id(record),
            resource_id=self._resource_id(record),
            holder_ref=f"sandbox-instance:{owner}",
            lease_epoch=record.lease_epoch,
            publication_timestamp=publication_timestamp,
            expiry_basis=self._expiry_basis(record),
            status=status,
            last_confirmed_observation=self._observation_ref(record),
            cleanup_eligibility_rule=f"sandbox_cleanup_policy:{record.policy_version}",
        )

    @staticmethod
    def _lease_id(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-lease:{record.sandbox_id}"

    @staticmethod
    def _resource_id(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-scope:{record.sandbox_id}"

    @staticmethod
    def _observation_ref(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-lifecycle:{record.sandbox_id}:{record.state.value}:{record.record_version}"

    @staticmethod
    def _expiry_basis(record: SandboxLifecycleRecord) -> str:
        expires_at = str(record.lease_expires_at or "none")
        return f"sandbox_lifecycle_policy:{record.policy_version};expires_at={expires_at}"

    @staticmethod
    def _status_for_record(record: SandboxLifecycleRecord) -> LeaseStatus:
        if record.state in {SandboxState.CREATING, SandboxState.STARTING}:
            return LeaseStatus.PENDING
        if record.state is SandboxState.ACTIVE:
            return LeaseStatus.ACTIVE
        if record.state is SandboxState.RECLAIMABLE and record.terminal_reason is TerminalReason.LEASE_EXPIRED:
            return LeaseStatus.EXPIRED
        if record.state is SandboxState.TERMINAL and record.terminal_reason is TerminalReason.LEASE_EXPIRED:
            return LeaseStatus.EXPIRED
        if record.state is SandboxState.TERMINAL and record.terminal_reason is TerminalReason.LOST_RUNTIME:
            return LeaseStatus.UNCERTAIN
        if record.state is SandboxState.CLEANED:
            return LeaseStatus.RELEASED
        raise SandboxControlPlaneLeaseError(
            "unsupported sandbox lifecycle state for lease publication: "
            f"{record.state.value}:{record.terminal_reason.value if record.terminal_reason else 'none'}"
        )


__all__ = [
    "SandboxControlPlaneLeaseError",
    "SandboxControlPlaneLeaseService",
]
