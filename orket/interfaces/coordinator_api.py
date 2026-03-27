from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_lease_service import CoordinatorControlPlaneLeaseService
from orket.application.services.coordinator_control_plane_reservation_service import (
    CoordinatorControlPlaneReservationService,
)
from orket.application.services.coordinator_store import (
    CoordinatorConflictError,
    CoordinatorNotFoundError,
    CoordinatorPermissionError,
    CoordinatorStoreError,
    CoordinatorValidationError,
    InMemoryCoordinatorStore,
)
from orket.core.domain.coordinator_card import Card
from orket.runtime_paths import resolve_control_plane_db_path


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_duration: float


class RenewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    lease_duration: float


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: dict | None = None


class FailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    result: dict | None = None


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


store = InMemoryCoordinatorStore()
control_plane_repository = AsyncControlPlaneRecordRepository(resolve_control_plane_db_path())
control_plane_publication = ControlPlanePublicationService(repository=control_plane_repository)
control_plane_lease_service = CoordinatorControlPlaneLeaseService(publication=control_plane_publication)
control_plane_reservation_service = CoordinatorControlPlaneReservationService(publication=control_plane_publication)

app = FastAPI()


def _http_exception_for_store_error(exc: CoordinatorStoreError) -> HTTPException:
    if isinstance(exc, CoordinatorValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, CoordinatorNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, CoordinatorPermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, CoordinatorConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="unexpected coordinator store error")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _snapshot_card_or_none(card_id: str) -> Card | None:
    try:
        return store.snapshot_card(card_id)
    except CoordinatorNotFoundError:
        return None


def _snapshot_cards() -> list[Card]:
    return store.snapshot_cards()


def _should_require_active_authority(*, card: Card | None, node_id: str) -> bool:
    if card is None or card.state != "CLAIMED" or card.hedged_execution:
        return False
    return str(card.claimed_by or "").strip() == str(node_id).strip()


def _reservation_summary(record) -> CoordinatorReservationSummary | None:
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


def _lease_summary(record) -> CoordinatorLeaseSummary | None:
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


def _resource_summary(record) -> CoordinatorResourceSummary | None:
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


async def _enrich_card_with_control_plane(card: Card) -> CoordinatorCardResponse:
    lease = await control_plane_repository.get_latest_lease_record(
        lease_id=control_plane_lease_service.lease_id_for(card.id)
    )
    resource = await control_plane_repository.get_latest_resource_record(
        resource_id=control_plane_lease_service.resource_id_for(card.id)
    )
    reservation = None
    if lease is not None and lease.source_reservation_id is not None:
        reservation = await control_plane_repository.get_latest_reservation_record(
            reservation_id=lease.source_reservation_id
        )
    payload = card.model_dump()
    payload["control_plane_reservation"] = _reservation_summary(reservation)
    payload["control_plane_lease"] = _lease_summary(lease)
    payload["control_plane_resource"] = _resource_summary(resource)
    return CoordinatorCardResponse.model_validate(payload)


@app.get("/cards", response_model=list[CoordinatorCardResponse])
async def get_cards(state: str = Query(default="open")) -> list[CoordinatorCardResponse]:
    if state.lower() != "open":
        raise HTTPException(status_code=400, detail='only "open" supported')
    previous_cards = await asyncio.to_thread(_snapshot_cards)
    observed_at = _utc_now()
    for previous_card in previous_cards:
        await control_plane_lease_service.publish_expired_from_snapshot(card=previous_card, observed_at=observed_at)
    try:
        cards = await asyncio.to_thread(store.list_open_cards)
    except CoordinatorStoreError as exc:
        raise _http_exception_for_store_error(exc) from exc
    return [await _enrich_card_with_control_plane(card) for card in cards]


@app.post("/cards/{id}/claim", response_model=CoordinatorCardResponse)
async def claim_card(id: str, request: ClaimRequest) -> CoordinatorCardResponse:
    previous_card = await asyncio.to_thread(_snapshot_card_or_none, id)
    observed_at = _utc_now()
    if previous_card is not None:
        await control_plane_lease_service.publish_expired_from_snapshot(card=previous_card, observed_at=observed_at)
    try:
        card = await asyncio.to_thread(store.claim, id, request.node_id, request.lease_duration)
    except CoordinatorStoreError as exc:
        raise _http_exception_for_store_error(exc) from exc
    lease_epoch = await control_plane_lease_service.next_claim_epoch(card_id=card.id, node_id=request.node_id)
    reservation = await control_plane_reservation_service.publish_claim_reservation(
        card=card,
        node_id=request.node_id,
        lease_epoch=lease_epoch,
        observed_at=observed_at,
    )
    await control_plane_lease_service.publish_claim(
        card=card,
        node_id=request.node_id,
        lease_duration=request.lease_duration,
        observed_at=observed_at,
        lease_epoch=lease_epoch,
        source_reservation_id=None if reservation is None else reservation.reservation_id,
    )
    if reservation is not None:
        await control_plane_reservation_service.promote_claim_reservation(
            card_id=card.id,
            lease_epoch=lease_epoch,
            observed_at=observed_at,
        )
    return await _enrich_card_with_control_plane(card)


@app.post("/cards/{id}/renew", response_model=CoordinatorCardResponse)
async def renew_card(id: str, request: RenewRequest) -> CoordinatorCardResponse:
    previous_card = await asyncio.to_thread(_snapshot_card_or_none, id)
    if _should_require_active_authority(card=previous_card, node_id=request.node_id):
        await control_plane_lease_service.require_active_authority(
            card_id=id,
            error_context="coordinator renew preflight",
        )
    try:
        card = await asyncio.to_thread(store.renew, id, request.node_id, request.lease_duration)
    except CoordinatorStoreError as exc:
        raise _http_exception_for_store_error(exc) from exc
    await control_plane_lease_service.publish_renew(
        card=card,
        node_id=request.node_id,
        lease_duration=request.lease_duration,
        observed_at=_utc_now(),
    )
    return await _enrich_card_with_control_plane(card)


@app.post("/cards/{id}/complete", response_model=CoordinatorCardResponse)
async def complete_card(id: str, request: CompleteRequest) -> CoordinatorCardResponse:
    previous_card = await asyncio.to_thread(_snapshot_card_or_none, id)
    if _should_require_active_authority(card=previous_card, node_id=request.node_id):
        await control_plane_lease_service.require_active_authority(
            card_id=id,
            error_context="coordinator complete preflight",
        )
    try:
        card = await asyncio.to_thread(store.complete, id, request.node_id, request.result)
    except CoordinatorStoreError as exc:
        raise _http_exception_for_store_error(exc) from exc
    await control_plane_lease_service.publish_release(
        card_id=id,
        node_id=request.node_id,
        final_state="complete",
        observed_at=_utc_now(),
    )
    return await _enrich_card_with_control_plane(card)


@app.post("/cards/{id}/fail", response_model=CoordinatorCardResponse)
async def fail_card(id: str, request: FailRequest) -> CoordinatorCardResponse:
    previous_card = await asyncio.to_thread(_snapshot_card_or_none, id)
    if _should_require_active_authority(card=previous_card, node_id=request.node_id):
        await control_plane_lease_service.require_active_authority(
            card_id=id,
            error_context="coordinator fail preflight",
        )
    try:
        card = await asyncio.to_thread(store.fail, id, request.node_id, request.result)
    except CoordinatorStoreError as exc:
        raise _http_exception_for_store_error(exc) from exc
    await control_plane_lease_service.publish_release(
        card_id=id,
        node_id=request.node_id,
        final_state="fail",
        observed_at=_utc_now(),
    )
    return await _enrich_card_with_control_plane(card)
