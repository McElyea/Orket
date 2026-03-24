from __future__ import annotations

from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import LeaseStatus, ReservationKind, ReservationStatus

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import LeaseRecord, ReservationRecord


class ControlPlaneReservationError(ValueError):
    """Raised when reservation or lease progression violates control-plane rules."""


TERMINAL_RESERVATION_STATUSES = frozenset(
    {
        ReservationStatus.PROMOTED_TO_LEASE,
        ReservationStatus.RELEASED,
        ReservationStatus.EXPIRED,
        ReservationStatus.CANCELLED,
        ReservationStatus.INVALIDATED,
    }
)

TERMINAL_LEASE_STATUSES = frozenset(
    {
        LeaseStatus.EXPIRED,
        LeaseStatus.RELEASED,
        LeaseStatus.REVOKED,
    }
)

_RESERVATION_STATUS_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    ReservationStatus.PENDING: frozenset(
        {
            ReservationStatus.ACTIVE,
            ReservationStatus.CANCELLED,
            ReservationStatus.INVALIDATED,
            ReservationStatus.EXPIRED,
            ReservationStatus.UNCERTAIN,
        }
    ),
    ReservationStatus.ACTIVE: frozenset(
        {
            ReservationStatus.PROMOTED_TO_LEASE,
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
            ReservationStatus.CANCELLED,
            ReservationStatus.INVALIDATED,
            ReservationStatus.UNCERTAIN,
        }
    ),
    ReservationStatus.UNCERTAIN: frozenset(
        {
            ReservationStatus.ACTIVE,
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
            ReservationStatus.CANCELLED,
            ReservationStatus.INVALIDATED,
        }
    ),
    ReservationStatus.PROMOTED_TO_LEASE: frozenset(),
    ReservationStatus.RELEASED: frozenset(),
    ReservationStatus.EXPIRED: frozenset(),
    ReservationStatus.CANCELLED: frozenset(),
    ReservationStatus.INVALIDATED: frozenset(),
}

_LEASE_STATUS_TRANSITIONS: dict[LeaseStatus, frozenset[LeaseStatus]] = {
    LeaseStatus.PENDING: frozenset(
        {
            LeaseStatus.ACTIVE,
            LeaseStatus.RELEASED,
            LeaseStatus.REVOKED,
            LeaseStatus.EXPIRED,
            LeaseStatus.UNCERTAIN,
        }
    ),
    LeaseStatus.ACTIVE: frozenset(
        {
            LeaseStatus.RELEASED,
            LeaseStatus.REVOKED,
            LeaseStatus.EXPIRED,
            LeaseStatus.UNCERTAIN,
        }
    ),
    LeaseStatus.UNCERTAIN: frozenset(
        {
            LeaseStatus.ACTIVE,
            LeaseStatus.RELEASED,
            LeaseStatus.REVOKED,
            LeaseStatus.EXPIRED,
        }
    ),
    LeaseStatus.RELEASED: frozenset(),
    LeaseStatus.REVOKED: frozenset(),
    LeaseStatus.EXPIRED: frozenset(),
}


def allowed_reservation_status_transitions(current_status: ReservationStatus) -> frozenset[ReservationStatus]:
    return _RESERVATION_STATUS_TRANSITIONS[current_status]


def allowed_lease_status_transitions(current_status: LeaseStatus) -> frozenset[LeaseStatus]:
    return _LEASE_STATUS_TRANSITIONS[current_status]


def validate_reservation_status_transition(*, current_status: ReservationStatus, next_status: ReservationStatus) -> bool:
    allowed = _RESERVATION_STATUS_TRANSITIONS[current_status]
    if next_status not in allowed:
        raise ControlPlaneReservationError(
            f"Illegal reservation status transition: {current_status.value} -> {next_status.value}."
        )
    return True


def validate_lease_status_transition(*, current_status: LeaseStatus, next_status: LeaseStatus) -> bool:
    allowed = _LEASE_STATUS_TRANSITIONS[current_status]
    if next_status not in allowed:
        raise ControlPlaneReservationError(
            f"Illegal lease status transition: {current_status.value} -> {next_status.value}."
        )
    return True


def reservation_publication_ref(record: ReservationRecord) -> str:
    return f"reservation:{record.reservation_id}:{record.status.value}"


def build_reservation_record(
    *,
    reservation_id: str,
    holder_ref: str,
    reservation_kind: ReservationKind,
    target_scope_ref: str,
    creation_timestamp: str,
    expiry_or_invalidation_basis: str,
    status: ReservationStatus,
    supervisor_authority_ref: str,
    promotion_rule: str | None = None,
    promoted_lease_id: str | None = None,
    previous_record: ReservationRecord | None = None,
) -> ReservationRecord:
    from orket.core.contracts.control_plane_models import ReservationRecord

    if previous_record is None and status not in {ReservationStatus.PENDING, ReservationStatus.ACTIVE}:
        raise ControlPlaneReservationError("initial reservation record must begin in pending or active status")

    history_refs: list[str] = []
    if previous_record is not None:
        validate_reservation_status_transition(current_status=previous_record.status, next_status=status)
        if previous_record.holder_ref != holder_ref:
            raise ControlPlaneReservationError("reservation holder_ref must remain stable across status updates")
        if previous_record.reservation_kind is not reservation_kind:
            raise ControlPlaneReservationError("reservation_kind must remain stable across status updates")
        if previous_record.target_scope_ref != target_scope_ref:
            raise ControlPlaneReservationError("target_scope_ref must remain stable across status updates")
        if previous_record.creation_timestamp != creation_timestamp:
            raise ControlPlaneReservationError("creation_timestamp must remain stable across status updates")
        history_refs = list(previous_record.history_refs)
        prior_ref = reservation_publication_ref(previous_record)
        if not history_refs or history_refs[-1] != prior_ref:
            history_refs.append(prior_ref)

    return ReservationRecord(
        reservation_id=str(reservation_id).strip(),
        holder_ref=str(holder_ref).strip(),
        reservation_kind=reservation_kind,
        target_scope_ref=str(target_scope_ref).strip(),
        creation_timestamp=str(creation_timestamp).strip(),
        expiry_or_invalidation_basis=str(expiry_or_invalidation_basis).strip(),
        status=status,
        promotion_rule=None if promotion_rule is None else str(promotion_rule).strip(),
        promoted_lease_id=None if promoted_lease_id is None else str(promoted_lease_id).strip(),
        supervisor_authority_ref=str(supervisor_authority_ref).strip(),
        history_refs=history_refs,
    )


def promote_reservation_to_lease(
    *,
    reservation: ReservationRecord,
    lease_id: str,
    resource_id: str,
    granted_timestamp: str,
    publication_timestamp: str | None = None,
    expiry_basis: str,
    cleanup_eligibility_rule: str,
) -> tuple[ReservationRecord, LeaseRecord]:
    from orket.core.contracts.control_plane_models import LeaseRecord

    if reservation.reservation_kind is not ReservationKind.RESOURCE:
        raise ControlPlaneReservationError("Only resource_reservation can promote to a lease.")
    validate_reservation_status_transition(
        current_status=reservation.status,
        next_status=ReservationStatus.PROMOTED_TO_LEASE,
    )
    promoted_reservation = reservation.model_copy(
        update={
            "status": ReservationStatus.PROMOTED_TO_LEASE,
            "promoted_lease_id": str(lease_id).strip(),
        }
    )
    lease = LeaseRecord(
        lease_id=str(lease_id).strip(),
        resource_id=str(resource_id).strip(),
        holder_ref=reservation.holder_ref,
        lease_epoch=0,
        granted_timestamp=str(granted_timestamp).strip(),
        publication_timestamp=str(publication_timestamp or granted_timestamp).strip(),
        expiry_basis=str(expiry_basis).strip(),
        status=LeaseStatus.ACTIVE,
        source_reservation_id=reservation.reservation_id,
        cleanup_eligibility_rule=str(cleanup_eligibility_rule).strip(),
    )
    return promoted_reservation, lease


__all__ = [
    "ControlPlaneReservationError",
    "TERMINAL_LEASE_STATUSES",
    "TERMINAL_RESERVATION_STATUSES",
    "allowed_lease_status_transitions",
    "allowed_reservation_status_transitions",
    "build_reservation_record",
    "promote_reservation_to_lease",
    "reservation_publication_ref",
    "validate_lease_status_transition",
    "validate_reservation_status_transition",
]
