from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import LeaseStatus
from orket.core.domain.control_plane_reservations import validate_lease_status_transition

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import LeaseRecord


class ControlPlaneLeaseError(ValueError):
    """Raised when lease publication violates control-plane lease authority."""


def lease_publication_ref(record: LeaseRecord) -> str:
    return f"lease-record:{record.lease_id}:{record.lease_epoch}:{record.publication_timestamp}"


def build_lease_record(
    *,
    lease_id: str,
    resource_id: str,
    holder_ref: str,
    lease_epoch: int,
    publication_timestamp: str,
    expiry_basis: str,
    status: LeaseStatus,
    cleanup_eligibility_rule: str,
    granted_timestamp: str | None = None,
    last_confirmed_observation: str | None = None,
    source_reservation_id: str | None = None,
    previous_record: LeaseRecord | None = None,
    history_refs: Sequence[str] = (),
) -> LeaseRecord:
    from orket.core.contracts.control_plane_models import LeaseRecord

    resolved_history = list(history_refs)
    resolved_granted_timestamp = str(granted_timestamp or publication_timestamp).strip()
    resolved_publication_timestamp = str(publication_timestamp).strip()

    if previous_record is not None:
        if previous_record.lease_id != str(lease_id).strip():
            raise ControlPlaneLeaseError("lease publication must not reuse a different prior lease_id")
        if lease_epoch < previous_record.lease_epoch:
            raise ControlPlaneLeaseError("lease publication must not decrease lease_epoch")
        if resolved_publication_timestamp < previous_record.publication_timestamp:
            raise ControlPlaneLeaseError("lease publication timestamps must increase monotonically")
        if (
            resolved_publication_timestamp == previous_record.publication_timestamp
            and lease_epoch == previous_record.lease_epoch
            and status is previous_record.status
        ):
            raise ControlPlaneLeaseError("same-status lease publication requires a newer publication_timestamp")
        resolved_history = list(previous_record.history_refs)
        previous_ref = lease_publication_ref(previous_record)
        if previous_ref not in resolved_history:
            resolved_history.append(previous_ref)
        if lease_epoch == previous_record.lease_epoch:
            if granted_timestamp is not None and resolved_granted_timestamp != previous_record.granted_timestamp:
                raise ControlPlaneLeaseError("same-epoch lease publication must preserve granted_timestamp")
            if status is not previous_record.status:
                validate_lease_status_transition(
                    current_status=previous_record.status,
                    next_status=status,
                )
            resolved_granted_timestamp = previous_record.granted_timestamp

    return LeaseRecord(
        lease_id=str(lease_id).strip(),
        resource_id=str(resource_id).strip(),
        holder_ref=str(holder_ref).strip(),
        lease_epoch=lease_epoch,
        granted_timestamp=resolved_granted_timestamp,
        publication_timestamp=resolved_publication_timestamp,
        expiry_basis=str(expiry_basis).strip(),
        status=status,
        last_confirmed_observation=(
            None if last_confirmed_observation is None else str(last_confirmed_observation).strip()
        ),
        source_reservation_id=None if source_reservation_id is None else str(source_reservation_id).strip(),
        cleanup_eligibility_rule=str(cleanup_eligibility_rule).strip(),
        history_refs=resolved_history,
    )


__all__ = [
    "ControlPlaneLeaseError",
    "build_lease_record",
    "lease_publication_ref",
]
