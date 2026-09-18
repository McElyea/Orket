"""Own one standalone coordinator's admitted transitions and publication lifetime."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.coordinator_control_plane_lease_service import CoordinatorControlPlaneLeaseService
from orket.application.services.coordinator_control_plane_reservation_service import (
    CoordinatorControlPlaneReservationService,
)
from orket.application.services.coordinator_read_service import CoordinatorCardResponse, coordinator_card_response
from orket.application.services.coordinator_store import (
    CoordinatorNotFoundError,
    CoordinatorStoreError,
    CoordinatorValidationError,
    InMemoryCoordinatorStore,
)
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError, canonical_json
from orket.core.domain.coordinator_card import Card

LOGGER = logging.getLogger(__name__)
_TRANSITION_OWNER: ContextVar[object | None] = ContextVar("coordinator_transition_owner", default=None)


class CoordinatorUnavailableError(RuntimeError):
    """Admission is closed or an earlier transition has unresolved failure."""


@dataclass(frozen=True)
class _Command:
    kind: str
    card_id: str
    node_id: str
    lease_duration: float
    result_json: str


@dataclass(frozen=True)
class _Observation:
    timestamp: str
    monotonic: float

    def __post_init__(self):
        if not isfinite(self.monotonic):
            raise CoordinatorValidationError("monotonic observation must be finite")


class CoordinatorRuntimeService:
    def __init__(
        self, *, project_root: Path | None = None, environment: Mapping[str, str] | None = None,
        runtime_inputs: RuntimeInputService | None = None, store: InMemoryCoordinatorStore | None = None,
        publication: ControlPlanePublicationService | None = None,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.environment = MappingProxyType(dict(os.environ if environment is None else environment))
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.store = store or InMemoryCoordinatorStore(monotonic_factory=self.runtime_inputs.monotonic_seconds)
        raw_root = self.environment.get("ORKET_DURABLE_ROOT", "").strip()
        durable = Path(raw_root) if raw_root else Path(".orket/durable")
        durable = durable if durable.is_absolute() else self.project_root / durable
        self._db_path = (durable / "db/control_plane_records.sqlite3").resolve() if publication is None else None
        self.publication = publication or ControlPlanePublicationService(
            repository=AsyncControlPlaneRecordRepository(self._db_path),
        )
        self.repository = self.publication.repository
        self.lease_service = CoordinatorControlPlaneLeaseService(
            publication=self.publication, runtime_inputs=self.runtime_inputs,
        )
        self.reservation_service = CoordinatorControlPlaneReservationService(
            publication=self.publication, runtime_inputs=self.runtime_inputs,
        )
        self._lock = asyncio.Lock()
        self._settled = asyncio.Event()
        self._settled.set()
        self._closing = False
        self._closed = False
        self._failure: BaseException | None = None
        self._active_caller: asyncio.Task | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    async def execute(
        self, kind: str, *, card_id: str = "", node_id: str = "", lease_duration: float = 0,
        result: dict[str, Any] | None = None,
    ) -> CoordinatorCardResponse | list[CoordinatorCardResponse]:
        try:
            command = _Command(kind, card_id, node_id, lease_duration, canonical_json(result))
        except ProtocolCanonicalizationError as exc:
            raise CoordinatorValidationError(str(exc)) from exc
        if kind not in {"list", "claim", "renew", "complete", "fail"}:
            raise ValueError("unknown coordinator operation")
        self._require_admission()
        async with self._lock:
            self._require_admission()
            self._settled.clear()
            self._active_caller = asyncio.current_task()
            try:
                return await run_owned_io(
                    lambda: self._transition(command), label="coordinator-" + kind, preserve_failure=True,
                )
            finally:
                self._active_caller = None
                self._settled.set()

    async def close(self) -> None:
        if asyncio.current_task() is self._active_caller or _TRANSITION_OWNER.get() is self:
            raise RuntimeError("A coordinator operation cannot await its own close")
        self._closing = True

        async def finish():
            await self._settled.wait()
            if self._failure is not None:
                raise RuntimeError("Coordinator has a failed transition; inspect retained state") from self._failure
            self._closed = True

        await run_owned_io(finish, label="coordinator-close", preserve_failure=True)

    def _require_admission(self) -> None:
        if self._closing or self._failure is not None:
            raise CoordinatorUnavailableError("Coordinator is closing or has an unresolved transition failure")

    async def _transition(self, command: _Command) -> CoordinatorCardResponse | list[CoordinatorCardResponse]:
        token = _TRANSITION_OWNER.set(self)
        try:
            if self._db_path is not None:
                await run_owned_thread(
                    lambda: self._db_path.parent.mkdir(parents=True, exist_ok=True), label="coordinator-storage-parent",
                )
            observed = _Observation(self.runtime_inputs.utc_now_iso(), self.runtime_inputs.monotonic_seconds())
            if command.kind == "list":
                snapshots = await run_owned_thread(self.store.snapshot_cards, label="coordinator-snapshot")
                for card in snapshots:
                    await self._expire(card, observed)
                cards = await run_owned_thread(
                    lambda: self.store.list_open_cards(now=observed.monotonic), label="coordinator-list",
                )
                return [await self._response(card) for card in cards]
            previous = await run_owned_thread(
                lambda: self._snapshot(command.card_id), label="coordinator-snapshot",
            )
            if command.kind == "claim":
                return await self._claim(command, previous, observed)
            if self._requires_authority(previous, command.node_id):
                await self.lease_service.require_active_authority(
                    card_id=command.card_id, error_context=f"coordinator {command.kind} preflight",
                )
            return await self._finish_or_renew(command, observed)
        except CoordinatorStoreError:
            raise
        except (Exception, asyncio.CancelledError) as exc:  # Transition supervisor retains uncertain effects.
            self._failure = exc
            LOGGER.exception("Coordinator transition failed", extra={"operation": command.kind, "card_id": command.card_id})
            raise
        finally:
            _TRANSITION_OWNER.reset(token)

    def _snapshot(self, card_id: str) -> Card | None:
        try:
            return self.store.snapshot_card(card_id)
        except CoordinatorNotFoundError:
            return None

    @staticmethod
    def _requires_authority(card: Card | None, node_id: str) -> bool:
        return bool(card is not None and card.state == "CLAIMED" and not card.hedged_execution
                    and str(card.claimed_by or "").strip() == str(node_id).strip())

    async def _expire(self, card: Card | None, observed: _Observation) -> None:
        if card is not None:
            await self.lease_service.publish_expired_from_snapshot(
                card=card, observed_at=observed.timestamp, observed_monotonic=observed.monotonic,
            )

    async def _response(self, card: Card) -> CoordinatorCardResponse:
        return await coordinator_card_response(card, repository=self.repository, lease_service=self.lease_service)

    async def _claim(self, command: _Command, previous: Card | None, observed: _Observation) -> CoordinatorCardResponse:
        await self._expire(previous, observed)
        card = await run_owned_thread(
            lambda: self.store.claim(command.card_id, command.node_id, command.lease_duration, now=observed.monotonic),
            label="coordinator-store-claim",
        )
        epoch = await self.lease_service.next_claim_epoch(card_id=card.id, node_id=command.node_id)
        reservation = await self.reservation_service.publish_claim_reservation(
            card=card, node_id=command.node_id, lease_epoch=epoch, observed_at=observed.timestamp,
        )
        await self.lease_service.publish_claim(
            card=card, node_id=command.node_id, lease_duration=command.lease_duration,
            observed_at=observed.timestamp, lease_epoch=epoch,
            source_reservation_id=None if reservation is None else reservation.reservation_id,
        )
        if reservation is not None:
            await self.reservation_service.promote_claim_reservation(
                card_id=card.id, lease_epoch=epoch, observed_at=observed.timestamp,
            )
        return await self._response(card)

    async def _finish_or_renew(self, command: _Command, observed: _Observation) -> CoordinatorCardResponse:
        if command.kind == "renew":
            card = await run_owned_thread(
                lambda: self.store.renew(command.card_id, command.node_id, command.lease_duration, now=observed.monotonic),
                label="coordinator-store-renew",
            )
            await self.lease_service.publish_renew(
                card=card, node_id=command.node_id, lease_duration=command.lease_duration, observed_at=observed.timestamp,
            )
        else:
            method = self.store.complete if command.kind == "complete" else self.store.fail
            card = await run_owned_thread(
                lambda: method(command.card_id, command.node_id, json.loads(command.result_json), now=observed.monotonic),
                label="coordinator-store-" + command.kind,
            )
            await self.lease_service.publish_release(
                card_id=command.card_id, node_id=command.node_id, final_state=command.kind,
                observed_at=observed.timestamp,
            )
        return await self._response(card)
