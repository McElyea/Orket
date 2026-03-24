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


def promote_reservation_to_lease(
    *,
    reservation: ReservationRecord,
    lease_id: str,
    resource_id: str,
    granted_timestamp: str,
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
    "promote_reservation_to_lease",
    "validate_lease_status_transition",
    "validate_reservation_status_transition",
]
