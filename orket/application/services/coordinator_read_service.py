"""Application response vocabulary and observed coordinator authority projection."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from orket.core.domain.coordinator_card import Card


class CoordinatorReservationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reservation_id: str
    reservation_kind: str
    status: str
    holder_ref: str
    target_scope_ref: str
    expiry_or_invalidation_basis: str
    supervisor_authority_ref: str
    promotion_rule: str | None = None
    promoted_lease_id: str | None = None


class CoordinatorLeaseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: str
    resource_id: str
    status: str
    holder_ref: str
    lease_epoch: int
    granted_timestamp: str
    publication_timestamp: str
    expiry_basis: str
    cleanup_eligibility_rule: str
    last_confirmed_observation: str | None = None
    source_reservation_id: str | None = None


class CoordinatorResourceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    resource_kind: str
    namespace_scope: str
    ownership_class: str
    current_observed_state: str
    last_observed_timestamp: str
    cleanup_authority_class: str
    provenance_ref: str
    reconciliation_status: str
    orphan_classification: str


class CoordinatorCardResponse(Card):
    model_config = ConfigDict(extra="forbid")

    control_plane_reservation: CoordinatorReservationSummary | None = None
    control_plane_lease: CoordinatorLeaseSummary | None = None
    control_plane_resource: CoordinatorResourceSummary | None = None


def _reservation_summary(record: Any) -> CoordinatorReservationSummary | None:
    if record is None:
        return None
    return CoordinatorReservationSummary(
        reservation_id=record.reservation_id,
        reservation_kind=record.reservation_kind.value,
        status=record.status.value,
        holder_ref=record.holder_ref,
        target_scope_ref=record.target_scope_ref,
        expiry_or_invalidation_basis=record.expiry_or_invalidation_basis,
        supervisor_authority_ref=record.supervisor_authority_ref,
        promotion_rule=record.promotion_rule,
        promoted_lease_id=record.promoted_lease_id,
    )


def _lease_summary(record: Any) -> CoordinatorLeaseSummary | None:
    if record is None:
        return None
    return CoordinatorLeaseSummary(
        lease_id=record.lease_id,
        resource_id=record.resource_id,
        status=record.status.value,
        holder_ref=record.holder_ref,
        lease_epoch=record.lease_epoch,
        granted_timestamp=record.granted_timestamp,
        publication_timestamp=record.publication_timestamp,
        expiry_basis=record.expiry_basis,
        cleanup_eligibility_rule=record.cleanup_eligibility_rule,
        last_confirmed_observation=record.last_confirmed_observation,
        source_reservation_id=record.source_reservation_id,
    )


def _resource_summary(record: Any) -> CoordinatorResourceSummary | None:
    if record is None:
        return None
    return CoordinatorResourceSummary(
        resource_id=record.resource_id,
        resource_kind=record.resource_kind,
        namespace_scope=record.namespace_scope,
        ownership_class=record.ownership_class.value,
        current_observed_state=record.current_observed_state,
        last_observed_timestamp=record.last_observed_timestamp,
        cleanup_authority_class=record.cleanup_authority_class.value,
        provenance_ref=record.provenance_ref,
        reconciliation_status=record.reconciliation_status,
        orphan_classification=record.orphan_classification.value,
    )


async def coordinator_card_response(
    card: Card, *, repository: Any, lease_service: Any,
) -> CoordinatorCardResponse:
    lease = await repository.get_latest_lease_record(
        lease_id=lease_service.lease_id_for(card.id)
    )
    resource = await repository.get_latest_resource_record(
        resource_id=lease_service.resource_id_for(card.id)
    )
    reservation = None
    if lease is not None and lease.source_reservation_id is not None:
        reservation = await repository.get_latest_reservation_record(
            reservation_id=lease.source_reservation_id
        )
    payload = card.model_dump()
    payload["control_plane_reservation"] = _reservation_summary(reservation)
    payload["control_plane_lease"] = _lease_summary(lease)
    payload["control_plane_resource"] = _resource_summary(resource)
    return CoordinatorCardResponse.model_validate(payload)
