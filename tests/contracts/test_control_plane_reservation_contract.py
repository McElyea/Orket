# Layer: contract

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.contracts import LeaseRecord, ReservationRecord
from orket.core.domain import (
    TERMINAL_LEASE_STATUSES,
    TERMINAL_RESERVATION_STATUSES,
    ControlPlaneReservationError,
    LeaseStatus,
    ReservationKind,
    ReservationStatus,
    allowed_lease_status_transitions,
    allowed_reservation_status_transitions,
    promote_reservation_to_lease,
    validate_lease_status_transition,
    validate_reservation_status_transition,
)

pytestmark = pytest.mark.contract


def _resource_reservation(*, status: ReservationStatus = ReservationStatus.ACTIVE) -> ReservationRecord:
    return ReservationRecord(
        reservation_id="res-1",
        holder_ref="run-1",
        reservation_kind=ReservationKind.RESOURCE,
        target_scope_ref="resource:sb-1",
        creation_timestamp="2026-03-23T00:00:00+00:00",
        expiry_or_invalidation_basis="ttl:300",
        status=status,
        supervisor_authority_ref="supervisor-1",
    )


def test_promoted_reservation_requires_promoted_lease_id() -> None:
    with pytest.raises(ValidationError, match="promoted reservation requires promoted_lease_id"):
        ReservationRecord(
            reservation_id="res-2",
            holder_ref="run-2",
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref="resource:sb-2",
            creation_timestamp="2026-03-23T00:00:00+00:00",
            expiry_or_invalidation_basis="ttl:300",
            status=ReservationStatus.PROMOTED_TO_LEASE,
            supervisor_authority_ref="supervisor-2",
        )


def test_non_promoted_reservation_rejects_promoted_lease_id() -> None:
    with pytest.raises(ValidationError, match="promoted_lease_id is only valid for promoted reservations"):
        ReservationRecord(
            reservation_id="res-3",
            holder_ref="run-3",
            reservation_kind=ReservationKind.RESOURCE,
            target_scope_ref="resource:sb-3",
            creation_timestamp="2026-03-23T00:00:00+00:00",
            expiry_or_invalidation_basis="ttl:300",
            status=ReservationStatus.ACTIVE,
            promoted_lease_id="lease-3",
            supervisor_authority_ref="supervisor-3",
        )


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        (ReservationStatus.PENDING, ReservationStatus.ACTIVE),
        (ReservationStatus.ACTIVE, ReservationStatus.PROMOTED_TO_LEASE),
        (ReservationStatus.ACTIVE, ReservationStatus.RELEASED),
        (LeaseStatus.PENDING, LeaseStatus.ACTIVE),
        (LeaseStatus.ACTIVE, LeaseStatus.RELEASED),
    ],
)
def test_reservation_and_lease_status_transitions_accept_required_paths(current_status, next_status) -> None:
    if isinstance(current_status, ReservationStatus):
        assert validate_reservation_status_transition(current_status=current_status, next_status=next_status) is True
    else:
        assert validate_lease_status_transition(current_status=current_status, next_status=next_status) is True


@pytest.mark.parametrize(
    ("current_status", "next_status"),
    [
        (ReservationStatus.PROMOTED_TO_LEASE, ReservationStatus.ACTIVE),
        (ReservationStatus.RELEASED, ReservationStatus.ACTIVE),
        (LeaseStatus.RELEASED, LeaseStatus.ACTIVE),
        (LeaseStatus.EXPIRED, LeaseStatus.PENDING),
    ],
)
def test_reservation_and_lease_status_transitions_reject_forbidden_paths(current_status, next_status) -> None:
    with pytest.raises(ControlPlaneReservationError):
        if isinstance(current_status, ReservationStatus):
            validate_reservation_status_transition(current_status=current_status, next_status=next_status)
        else:
            validate_lease_status_transition(current_status=current_status, next_status=next_status)


def test_promote_resource_reservation_to_lease() -> None:
    promoted, lease = promote_reservation_to_lease(
        reservation=_resource_reservation(),
        lease_id="lease-1",
        resource_id="resource:sb-1",
        granted_timestamp="2026-03-23T00:01:00+00:00",
        publication_timestamp="2026-03-23T00:01:00+00:00",
        expiry_basis="ttl:300",
        cleanup_eligibility_rule="cleanup_on_terminal",
    )

    assert promoted.status is ReservationStatus.PROMOTED_TO_LEASE
    assert promoted.promoted_lease_id == "lease-1"
    assert lease.status is LeaseStatus.ACTIVE
    assert lease.source_reservation_id == "res-1"


def test_promote_non_resource_reservation_to_lease_rejected() -> None:
    reservation = ReservationRecord(
        reservation_id="res-4",
        holder_ref="run-4",
        reservation_kind=ReservationKind.CONCURRENCY,
        target_scope_ref="namespace:control-plane",
        creation_timestamp="2026-03-23T00:00:00+00:00",
        expiry_or_invalidation_basis="ttl:300",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref="supervisor-4",
    )

    with pytest.raises(ControlPlaneReservationError, match="Only resource_reservation can promote"):
        promote_reservation_to_lease(
            reservation=reservation,
            lease_id="lease-4",
            resource_id="resource:none",
            granted_timestamp="2026-03-23T00:01:00+00:00",
            publication_timestamp="2026-03-23T00:01:00+00:00",
            expiry_basis="ttl:300",
            cleanup_eligibility_rule="cleanup_on_terminal",
        )


def test_terminal_status_sets_match_contract() -> None:
    assert frozenset(
        {
            ReservationStatus.PROMOTED_TO_LEASE,
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
            ReservationStatus.CANCELLED,
            ReservationStatus.INVALIDATED,
        }
    ) == TERMINAL_RESERVATION_STATUSES
    assert frozenset(
        {
            LeaseStatus.EXPIRED,
            LeaseStatus.RELEASED,
            LeaseStatus.REVOKED,
        }
    ) == TERMINAL_LEASE_STATUSES


def test_allowed_status_transition_helpers_expose_closed_terminal_states() -> None:
    assert allowed_reservation_status_transitions(ReservationStatus.RELEASED) == frozenset()
    assert allowed_lease_status_transitions(LeaseStatus.REVOKED) == frozenset()


def test_lease_record_accepts_promoted_reservation_reference() -> None:
    lease = LeaseRecord(
        lease_id="lease-5",
        resource_id="resource:sb-5",
        holder_ref="run-5",
        lease_epoch=0,
        granted_timestamp="2026-03-23T00:00:00+00:00",
        publication_timestamp="2026-03-23T00:00:00+00:00",
        expiry_basis="ttl:300",
        status=LeaseStatus.ACTIVE,
        source_reservation_id="res-5",
        cleanup_eligibility_rule="cleanup_on_terminal",
    )

    assert lease.source_reservation_id == "res-5"
