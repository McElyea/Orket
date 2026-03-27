from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import LeaseRecord, ResourceRecord
from orket.core.domain import CleanupAuthorityClass, LeaseStatus, OrphanClassification, OwnershipClass
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


class SandboxControlPlaneResourceService:
    """Publishes sandbox lifecycle state through the shared ResourceRecord family."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_from_record(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> ResourceRecord:
        latest = await self.publication.repository.get_latest_resource_record(
            resource_id=self.resource_id_for_sandbox(record.sandbox_id)
        )
        current_state = self._current_observed_state(record)
        if (
            latest is not None
            and latest.last_observed_timestamp == observed_at
            and latest.current_observed_state == current_state
        ):
            return latest
        return await self.publication.publish_resource(
            resource_id=self.resource_id_for_sandbox(record.sandbox_id),
            resource_kind="sandbox_runtime",
            namespace_scope=self.namespace_scope_for_sandbox(record.sandbox_id),
            ownership_class=self._ownership_class(record),
            current_observed_state=current_state,
            last_observed_timestamp=observed_at,
            cleanup_authority_class=self._cleanup_authority_class(record),
            provenance_ref=self._provenance_ref(record),
            reconciliation_status=self._reconciliation_status(record),
            orphan_classification=self._orphan_classification(record),
        )

    async def publish_from_lease_closeout(
        self,
        *,
        sandbox_id: str,
        lease: LeaseRecord,
        observed_at: str,
        closeout_basis: str,
    ) -> ResourceRecord:
        current_state = (
            f"lease_status:{lease.status.value};"
            f"closeout_basis:{str(closeout_basis).strip()};"
            "lifecycle_record_unavailable"
        )
        resource_id = self.resource_id_for_sandbox(sandbox_id)
        latest = await self.publication.repository.get_latest_resource_record(resource_id=resource_id)
        if (
            latest is not None
            and latest.last_observed_timestamp == observed_at
            and latest.current_observed_state == current_state
        ):
            return latest
        return await self.publication.publish_resource(
            resource_id=resource_id,
            resource_kind="sandbox_runtime",
            namespace_scope=self.namespace_scope_for_sandbox(sandbox_id),
            ownership_class=OwnershipClass.RUN_OWNED,
            current_observed_state=current_state,
            last_observed_timestamp=observed_at,
            cleanup_authority_class=self._cleanup_authority_class_for_lease(lease),
            provenance_ref=lease.last_confirmed_observation or f"sandbox-lease:{sandbox_id}:{lease.status.value}",
            reconciliation_status="lifecycle_record_unavailable",
            orphan_classification=self._orphan_classification_for_lease(lease),
        )

    @staticmethod
    def resource_id_for_sandbox(sandbox_id: str) -> str:
        return f"sandbox-scope:{sandbox_id}"

    @staticmethod
    def namespace_scope_for_sandbox(sandbox_id: str) -> str:
        return f"sandbox-scope:{sandbox_id}"

    @staticmethod
    def _provenance_ref(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-lifecycle:{record.sandbox_id}:{record.state.value}:{record.record_version}"

    @staticmethod
    def _reconciliation_status(record: SandboxLifecycleRecord) -> str:
        return "reconciliation_required" if record.requires_reconciliation else "reconciliation_not_required"

    @classmethod
    def _current_observed_state(cls, record: SandboxLifecycleRecord) -> str:
        terminal_reason = "none" if record.terminal_reason is None else record.terminal_reason.value
        return (
            f"sandbox_state:{record.state.value};"
            f"cleanup_state:{record.cleanup_state.value};"
            f"lease_epoch:{record.lease_epoch};"
            f"terminal_reason:{terminal_reason};"
            f"{cls._reconciliation_status(record)}"
        )

    @staticmethod
    def _ownership_class(record: SandboxLifecycleRecord) -> OwnershipClass:
        if record.state in {SandboxState.CLEANED, SandboxState.ORPHANED}:
            return OwnershipClass.EXTERNAL_UNOWNED_REFERENCE
        return OwnershipClass.RUN_OWNED

    @staticmethod
    def _cleanup_authority_class(record: SandboxLifecycleRecord) -> CleanupAuthorityClass:
        if record.state is SandboxState.CLEANED:
            return CleanupAuthorityClass.ADAPTER_CLEANUP_ONLY
        if record.state is SandboxState.ORPHANED:
            return CleanupAuthorityClass.OPERATOR_CLEANUP_REQUIRED
        if record.requires_reconciliation or record.terminal_reason is TerminalReason.LOST_RUNTIME:
            return CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION
        if record.state in {SandboxState.TERMINAL, SandboxState.RECLAIMABLE}:
            return CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED
        return CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION

    @staticmethod
    def _orphan_classification(record: SandboxLifecycleRecord) -> OrphanClassification:
        if record.state is SandboxState.ORPHANED:
            return OrphanClassification.VERIFIED_ORPHAN
        if record.terminal_reason is TerminalReason.LOST_RUNTIME or record.requires_reconciliation:
            return OrphanClassification.SUSPECTED_ORPHAN
        return OrphanClassification.NOT_ORPHANED

    @staticmethod
    def _cleanup_authority_class_for_lease(lease: LeaseRecord) -> CleanupAuthorityClass:
        if lease.status is LeaseStatus.UNCERTAIN:
            return CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION
        return CleanupAuthorityClass.ADAPTER_CLEANUP_ONLY

    @staticmethod
    def _orphan_classification_for_lease(lease: LeaseRecord) -> OrphanClassification:
        if lease.status is LeaseStatus.UNCERTAIN:
            return OrphanClassification.SUSPECTED_ORPHAN
        return OrphanClassification.NOT_ORPHANED


__all__ = ["SandboxControlPlaneResourceService"]
