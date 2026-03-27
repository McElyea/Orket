from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import LeaseRecord, ReservationRecord, RunRecord
from orket.core.domain import LeaseStatus, ReservationKind, ReservationStatus


class KernelActionControlPlaneResourceError(ValueError):
    """Raised when kernel-action reservation or lease truth cannot be published honestly."""


PROMOTION_RULE = "promote_on_kernel_action_execution_start"
CLEANUP_RULE = "release_kernel_action_execution_authority_on_terminal_closeout"


def reservation_id_for_run(*, run_id: str) -> str:
    return f"kernel-action-reservation:{run_id}"


def lease_id_for_run(*, run_id: str) -> str:
    return f"kernel-action-lease:{run_id}"


def holder_ref_for_run(*, run_id: str) -> str:
    return f"kernel-action-run:{run_id}"


def target_scope_ref_for_run(*, run: RunRecord) -> str:
    namespace_scope = str(run.namespace_scope or "").strip()
    if namespace_scope:
        return f"kernel-action-scope:{namespace_scope}"
    return f"kernel-action-scope:{run.run_id}"


async def ensure_admission_reservation(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
) -> ReservationRecord:
    reservation_id = reservation_id_for_run(run_id=run.run_id)
    existing = await publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
    if existing is not None:
        return existing
    return await publication.publish_reservation(
        reservation_id=reservation_id,
        holder_ref=holder_ref_for_run(run_id=run.run_id),
        reservation_kind=ReservationKind.CONCURRENCY,
        target_scope_ref=target_scope_ref_for_run(run=run),
        creation_timestamp=run.creation_timestamp,
        expiry_or_invalidation_basis="kernel_action_admission_reserved",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"kernel-action-supervisor:{run.run_id}:admit",
        promotion_rule=PROMOTION_RULE,
    )


async def ensure_active_execution_lease(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    publication_timestamp: str,
) -> tuple[ReservationRecord, LeaseRecord]:
    reservation = await ensure_admission_reservation(publication=publication, run=run)
    if reservation.status not in {ReservationStatus.ACTIVE, ReservationStatus.PROMOTED_TO_LEASE}:
        raise KernelActionControlPlaneResourceError(
            f"kernel-action run {run.run_id} requires active reservation before execution"
        )
    lease_id = lease_id_for_run(run_id=run.run_id)
    lease = await publication.repository.get_latest_lease_record(lease_id=lease_id)
    if lease is None:
        lease = await publication.publish_lease(
            lease_id=lease_id,
            resource_id=target_scope_ref_for_run(run=run),
            holder_ref=holder_ref_for_run(run_id=run.run_id),
            lease_epoch=1,
            publication_timestamp=publication_timestamp,
            expiry_basis="kernel_action_execution_active",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule=CLEANUP_RULE,
            source_reservation_id=reservation.reservation_id,
        )
    elif lease.status is not LeaseStatus.ACTIVE:
        raise KernelActionControlPlaneResourceError(
            f"kernel-action run {run.run_id} cannot continue from non-active execution lease"
        )
    if reservation.status is ReservationStatus.PROMOTED_TO_LEASE:
        return reservation, lease
    try:
        reservation = await publication.promote_reservation_to_lease(
            reservation_id=reservation.reservation_id,
            promoted_lease_id=lease.lease_id,
            supervisor_authority_ref=f"kernel-action-supervisor:{run.run_id}:promote_execution_lease",
            promotion_basis="kernel_action_execution_started",
        )
    except Exception:
        await _rollback_execution_activation_failure(
            publication=publication,
            run=run,
            lease=lease,
            publication_timestamp=publication_timestamp,
        )
        raise
    return reservation, lease


async def release_execution_authority_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    release_basis: str,
    publication_timestamp: str,
) -> tuple[ReservationRecord | None, LeaseRecord | None]:
    lease = await _release_lease_if_present(
        publication=publication,
        run=run,
        release_basis=release_basis,
        publication_timestamp=publication_timestamp,
    )
    reservation = await _release_reservation_if_present(
        publication=publication,
        run=run,
        release_basis=release_basis,
    )
    return reservation, lease


async def _release_lease_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    release_basis: str,
    publication_timestamp: str,
) -> LeaseRecord | None:
    lease_id = lease_id_for_run(run_id=run.run_id)
    existing = await publication.repository.get_latest_lease_record(lease_id=lease_id)
    if existing is None or existing.status in {LeaseStatus.RELEASED, LeaseStatus.REVOKED, LeaseStatus.EXPIRED}:
        return existing
    return await publication.publish_lease(
        lease_id=existing.lease_id,
        resource_id=existing.resource_id,
        holder_ref=existing.holder_ref,
        lease_epoch=existing.lease_epoch,
        publication_timestamp=publication_timestamp,
        expiry_basis=release_basis,
        status=LeaseStatus.RELEASED,
        cleanup_eligibility_rule=existing.cleanup_eligibility_rule,
        last_confirmed_observation=existing.last_confirmed_observation,
        source_reservation_id=existing.source_reservation_id,
    )


async def _release_reservation_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    release_basis: str,
) -> ReservationRecord | None:
    reservation_id = reservation_id_for_run(run_id=run.run_id)
    existing = await publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
    if existing is None or existing.status in {
        ReservationStatus.RELEASED,
        ReservationStatus.CANCELLED,
        ReservationStatus.INVALIDATED,
        ReservationStatus.EXPIRED,
        ReservationStatus.PROMOTED_TO_LEASE,
    }:
        return existing
    return await publication.release_reservation(
        reservation_id=reservation_id,
        supervisor_authority_ref=f"kernel-action-supervisor:{run.run_id}:release_reservation",
        release_basis=release_basis,
    )


async def _rollback_execution_activation_failure(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    lease: LeaseRecord,
    publication_timestamp: str,
) -> None:
    if lease.status is LeaseStatus.ACTIVE:
        await publication.publish_lease(
            lease_id=lease.lease_id,
            resource_id=lease.resource_id,
            holder_ref=lease.holder_ref,
            lease_epoch=lease.lease_epoch,
            publication_timestamp=publication_timestamp,
            expiry_basis="kernel_action_execution_activation_failed",
            status=LeaseStatus.RELEASED,
            cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
            last_confirmed_observation=lease.last_confirmed_observation,
            source_reservation_id=lease.source_reservation_id,
        )
    reservation = await publication.repository.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=run.run_id)
    )
    if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
        await publication.invalidate_reservation(
            reservation_id=reservation.reservation_id,
            supervisor_authority_ref=f"kernel-action-supervisor:{run.run_id}:activation_fail_closeout",
            invalidation_basis="kernel_action_execution_activation_failed",
        )


__all__ = [
    "KernelActionControlPlaneResourceError",
    "ensure_active_execution_lease",
    "ensure_admission_reservation",
    "holder_ref_for_run",
    "lease_id_for_run",
    "release_execution_authority_if_present",
    "reservation_id_for_run",
    "target_scope_ref_for_run",
]
