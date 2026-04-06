from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import ReservationRecord
from orket.core.domain import ReservationKind, ReservationStatus
from orket.core.domain.sandbox import PortAllocation


class SandboxControlPlaneReservationError(ValueError):
    """Raised when sandbox reservation truth cannot be published honestly."""


class SandboxControlPlaneReservationService:
    """Publishes sandbox allocation reservations and explicit reservation-to-lease promotion."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_allocation_reservation(
        self,
        *,
        sandbox_id: str,
        run_id: str,
        compose_project: str,
        ports: PortAllocation,
        creation_timestamp: str,
        instance_id: str,
    ) -> ReservationRecord:
        if not run_id.strip():
            raise SandboxControlPlaneReservationError("sandbox allocation reservation requires run_id")
        return await self.publication.publish_reservation(
            reservation_id=self.reservation_id_for_sandbox(sandbox_id),
            holder_ref=f"sandbox-run:{run_id}",
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref=self._target_scope_ref(
                sandbox_id=sandbox_id,
                compose_project=compose_project,
                ports=ports,
            ),
            creation_timestamp=creation_timestamp,
            expiry_or_invalidation_basis="sandbox_create_flow_allocation",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"sandbox-orchestrator:{instance_id}:port-allocation",
            promotion_rule="promote_on_lifecycle_record_creation",
        )

    async def promote_allocation_reservation(
        self,
        *,
        sandbox_id: str,
        instance_id: str,
    ) -> ReservationRecord:
        return await self.publication.promote_reservation_to_lease(
            reservation_id=self.reservation_id_for_sandbox(sandbox_id),
            promoted_lease_id=self.lease_id_for_sandbox(sandbox_id),
            supervisor_authority_ref=f"sandbox-lifecycle:{sandbox_id}:create_record:{instance_id}",
            promotion_basis="sandbox_lifecycle_record_created",
        )

    async def invalidate_allocation_reservation(
        self,
        *,
        sandbox_id: str,
        instance_id: str,
        invalidation_basis: str,
    ) -> ReservationRecord:
        return await self.publication.invalidate_reservation(
            reservation_id=self.reservation_id_for_sandbox(sandbox_id),
            supervisor_authority_ref=f"sandbox-orchestrator:{instance_id}:allocation-invalidation",
            invalidation_basis=invalidation_basis,
        )

    @staticmethod
    def reservation_id_for_sandbox(sandbox_id: str) -> str:
        return f"sandbox-reservation:{sandbox_id}"

    @staticmethod
    def lease_id_for_sandbox(sandbox_id: str) -> str:
        return f"sandbox-lease:{sandbox_id}"

    @staticmethod
    def _target_scope_ref(
        *,
        sandbox_id: str,
        compose_project: str,
        ports: PortAllocation,
    ) -> str:
        admin_port = "none" if ports.admin_tool is None else str(ports.admin_tool)
        return (
            f"sandbox-allocation:{sandbox_id}:compose={compose_project}:"
            f"api={ports.api}:frontend={ports.frontend}:database={ports.database}:admin={admin_port}"
        )


__all__ = [
    "SandboxControlPlaneReservationError",
    "SandboxControlPlaneReservationService",
]
