from __future__ import annotations

from dataclasses import dataclass

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_closure_service import SandboxControlPlaneClosureService
from orket.application.services.sandbox_control_plane_lease_service import SandboxControlPlaneLeaseService
from orket.core.contracts import FinalTruthRecord, ReconciliationRecord
from orket.core.domain import (
    DivergenceClass,
    ResidualUncertaintyClassification,
    SafeContinuationClass,
)
from orket.core.domain.sandbox_lifecycle import TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


class SandboxControlPlaneReconciliationError(ValueError):
    """Raised when sandbox reconciliation cannot publish control-plane truth."""


@dataclass(frozen=True)
class SandboxPublishedReconciliation:
    reconciliation_record: ReconciliationRecord
    final_truth: FinalTruthRecord | None = None


class SandboxControlPlaneReconciliationService:
    """Publishes durable reconciliation truth for sandbox runtime mismatches."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication
        self.closure = SandboxControlPlaneClosureService(publication=publication)
        self.leases = SandboxControlPlaneLeaseService(publication=publication)

    async def publish_lost_runtime_reconciliation(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxPublishedReconciliation:
        if record.run_id is None:
            raise SandboxControlPlaneReconciliationError("lost_runtime reconciliation requires run_id")
        if record.terminal_reason is not TerminalReason.LOST_RUNTIME:
            raise SandboxControlPlaneReconciliationError(
                "lost_runtime reconciliation publication requires terminal_reason=lost_runtime"
            )
        await self.leases.publish_from_record(record=record, publication_timestamp=observed_at)
        reconciliation = await self.publication.publish_reconciliation(
            reconciliation_id=self._reconciliation_id(record),
            target_ref=record.run_id,
            comparison_scope="run_scope",
            observed_refs=[f"sandbox-observation:{record.sandbox_id}:docker_absent:{observed_at}"],
            intended_refs=[
                f"sandbox-lifecycle:{record.sandbox_id}:state=active",
                f"sandbox-runtime:{record.compose_project}:docker_present",
            ],
            divergence_class=DivergenceClass.RESOURCE_STATE_DIVERGED,
            residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
            publication_timestamp=observed_at,
            safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
        )
        final_truth = await self.closure.publish_terminal_final_truth(
            record=record,
            reconciliation_record=reconciliation,
        )
        return SandboxPublishedReconciliation(
            reconciliation_record=reconciliation,
            final_truth=final_truth,
        )

    async def publish_reclaimable_reconciliation(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxPublishedReconciliation:
        if record.run_id is None:
            raise SandboxControlPlaneReconciliationError("reclaimable reconciliation requires run_id")
        if record.terminal_reason is not TerminalReason.LEASE_EXPIRED:
            raise SandboxControlPlaneReconciliationError(
                "reclaimable reconciliation publication requires terminal_reason=lease_expired"
            )
        await self.leases.publish_from_record(record=record, publication_timestamp=observed_at)
        reconciliation = await self.publication.publish_reconciliation(
            reconciliation_id=self._reconciliation_id(record),
            target_ref=record.run_id,
            comparison_scope="resource_set",
            observed_refs=[f"sandbox-observation:{record.sandbox_id}:docker_present:{observed_at}"],
            intended_refs=[
                f"sandbox-lease:{record.sandbox_id}:lease_expired",
                f"sandbox-runtime:{record.compose_project}:continued_presence",
            ],
            divergence_class=DivergenceClass.OWNERSHIP_DIVERGED,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            publication_timestamp=observed_at,
            safe_continuation_class=SafeContinuationClass.UNSAFE_TO_CONTINUE,
        )
        return SandboxPublishedReconciliation(reconciliation_record=reconciliation)

    async def publish_cleaned_externally_reconciliation(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxPublishedReconciliation:
        if record.run_id is None:
            raise SandboxControlPlaneReconciliationError("cleaned_externally reconciliation requires run_id")
        if record.terminal_reason is not TerminalReason.CLEANED_EXTERNALLY:
            raise SandboxControlPlaneReconciliationError(
                "cleaned_externally reconciliation publication requires terminal_reason=cleaned_externally"
            )
        await self.leases.publish_from_record(record=record, publication_timestamp=observed_at)
        reconciliation = await self.publication.publish_reconciliation(
            reconciliation_id=self._reconciliation_id(record),
            target_ref=record.run_id,
            comparison_scope="cleanup_scope",
            observed_refs=[f"sandbox-observation:{record.sandbox_id}:docker_absent:{observed_at}"],
            intended_refs=[f"sandbox-cleanup:{record.sandbox_id}:absence_required"],
            divergence_class=DivergenceClass.EXPECTED_EFFECT_OBSERVED,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            publication_timestamp=observed_at,
            safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
        )
        return SandboxPublishedReconciliation(reconciliation_record=reconciliation)

    @staticmethod
    def _reconciliation_id(record: SandboxLifecycleRecord) -> str:
        if record.run_id is None:
            raise SandboxControlPlaneReconciliationError("sandbox reconciliation id requires run_id")
        return f"sandbox-reconciliation:{record.run_id}:{record.record_version:08d}"


__all__ = [
    "SandboxControlPlaneReconciliationError",
    "SandboxControlPlaneReconciliationService",
    "SandboxPublishedReconciliation",
]
