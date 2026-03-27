from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import LeaseRecord, ReservationRecord, ResourceRecord, RunRecord
from orket.core.domain import (
    CleanupAuthorityClass,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
    ReservationKind,
    ReservationStatus,
)


class TurnToolControlPlaneResourceError(ValueError):
    """Raised when governed turn reservation or lease truth cannot be published honestly."""


PROMOTION_RULE = "promote_on_turn_execution_start"
CLEANUP_RULE = "release_namespace_authority_on_turn_closeout"


def reservation_id_for_run(*, run_id: str) -> str:
    return f"turn-tool-reservation:{run_id}"


def lease_id_for_run(*, run_id: str) -> str:
    return f"turn-tool-lease:{run_id}"


def namespace_resource_id_for_scope(*, namespace_scope: str) -> str:
    scope = str(namespace_scope).strip()
    if not scope:
        raise TurnToolControlPlaneResourceError("namespace scope is required for turn-tool resource authority")
    return f"namespace:{scope}"


def namespace_resource_id_for_run(*, run: RunRecord) -> str:
    return namespace_resource_id_for_scope(namespace_scope=_namespace_scope(run))


def holder_ref_for_run(*, run_id: str) -> str:
    return f"turn-tool-run:{run_id}"


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
        reservation_kind=ReservationKind.NAMESPACE,
        target_scope_ref=namespace_resource_id_for_run(run=run),
        creation_timestamp=run.creation_timestamp,
        expiry_or_invalidation_basis="turn_tool_admission_reserved",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}:admit",
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
        raise TurnToolControlPlaneResourceError(
            f"governed turn run {run.run_id} requires active namespace reservation before execution"
        )
    lease_id = lease_id_for_run(run_id=run.run_id)
    lease = await publication.repository.get_latest_lease_record(lease_id=lease_id)
    if lease is None:
        lease = await publication.publish_lease(
            lease_id=lease_id,
            resource_id=namespace_resource_id_for_run(run=run),
            holder_ref=holder_ref_for_run(run_id=run.run_id),
            lease_epoch=1,
            publication_timestamp=publication_timestamp,
            expiry_basis="turn_tool_execution_active",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule=CLEANUP_RULE,
            source_reservation_id=reservation.reservation_id,
        )
    elif lease.status is not LeaseStatus.ACTIVE:
        raise TurnToolControlPlaneResourceError(
            f"governed turn run {run.run_id} cannot resume from non-active namespace lease"
        )
    await publish_resource_snapshot(publication=publication, run=run, lease=lease)
    if reservation.status is ReservationStatus.PROMOTED_TO_LEASE:
        return reservation, lease
    try:
        reservation = await publication.promote_reservation_to_lease(
            reservation_id=reservation.reservation_id,
            promoted_lease_id=lease.lease_id,
            supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}:promote_namespace_lease",
            promotion_basis="turn_tool_execution_started",
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


async def invalidate_admission_reservation_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    invalidation_basis: str,
) -> ReservationRecord | None:
    reservation_id = reservation_id_for_run(run_id=run.run_id)
    existing = await publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
    if existing is None or existing.status in {
        ReservationStatus.INVALIDATED,
        ReservationStatus.RELEASED,
        ReservationStatus.CANCELLED,
        ReservationStatus.EXPIRED,
    }:
        return existing
    if existing.status is ReservationStatus.PROMOTED_TO_LEASE:
        raise TurnToolControlPlaneResourceError(
            f"governed turn run {run.run_id} cannot invalidate promoted namespace reservation after execution start"
        )
    return await publication.invalidate_reservation(
        reservation_id=reservation_id,
        supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}:invalidate_namespace_reservation",
        invalidation_basis=invalidation_basis,
    )


async def release_execution_authority_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    release_basis: str,
    publication_timestamp: str,
) -> tuple[ReservationRecord | None, LeaseRecord | None]:
    lease = await _release_execution_lease_if_present(
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


async def _release_execution_lease_if_present(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    release_basis: str,
    publication_timestamp: str,
) -> LeaseRecord | None:
    lease_id = lease_id_for_run(run_id=run.run_id)
    existing = await publication.repository.get_latest_lease_record(lease_id=lease_id)
    if existing is None or existing.status in {
        LeaseStatus.RELEASED,
        LeaseStatus.REVOKED,
        LeaseStatus.EXPIRED,
    }:
        return existing
    released = await publication.publish_lease(
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
    await publish_resource_snapshot(publication=publication, run=run, lease=released)
    return released


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
    }:
        return existing
    if existing.status is ReservationStatus.PROMOTED_TO_LEASE:
        return existing
    return await publication.release_reservation(
        reservation_id=reservation_id,
        supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}:release_namespace_reservation",
        release_basis=release_basis,
    )


def _namespace_scope(run: RunRecord) -> str:
    namespace_scope = str(run.namespace_scope or "").strip()
    if not namespace_scope:
        raise TurnToolControlPlaneResourceError(
            f"governed turn run {run.run_id} is missing namespace scope for reservation or lease authority"
        )
    return namespace_scope


async def _rollback_execution_activation_failure(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    lease: LeaseRecord,
    publication_timestamp: str,
) -> None:
    if lease.status is LeaseStatus.ACTIVE:
        released = await publication.publish_lease(
            lease_id=lease.lease_id,
            resource_id=lease.resource_id,
            holder_ref=lease.holder_ref,
            lease_epoch=lease.lease_epoch,
            publication_timestamp=publication_timestamp,
            expiry_basis="turn_tool_execution_activation_failed",
            status=LeaseStatus.RELEASED,
            cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
            last_confirmed_observation=lease.last_confirmed_observation,
            source_reservation_id=lease.source_reservation_id,
        )
        await publish_resource_snapshot(publication=publication, run=run, lease=released)
    reservation = await publication.repository.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=run.run_id)
    )
    if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
        await publication.invalidate_reservation(
            reservation_id=reservation.reservation_id,
            supervisor_authority_ref=f"turn-tool-supervisor:{run.run_id}:activation_fail_closeout",
            invalidation_basis="turn_tool_execution_activation_failed",
        )


async def publish_resource_snapshot(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    lease: LeaseRecord,
) -> ResourceRecord:
    namespace_scope = _namespace_scope(run)
    return await publication.publish_resource(
        resource_id=namespace_resource_id_for_run(run=run),
        resource_kind="turn_tool_namespace",
        namespace_scope=namespace_scope,
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state=f"lease_status:{lease.status.value};namespace:{namespace_scope}",
        last_observed_timestamp=lease.publication_timestamp,
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref=lease.last_confirmed_observation or lease.lease_id,
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )


__all__ = [
    "TurnToolControlPlaneResourceError",
    "ensure_active_execution_lease",
    "ensure_admission_reservation",
    "holder_ref_for_run",
    "invalidate_admission_reservation_if_present",
    "lease_id_for_run",
    "namespace_resource_id_for_scope",
    "namespace_resource_id_for_run",
    "release_execution_authority_if_present",
    "reservation_id_for_run",
]
