"""Captured workload context; application callbacks admit emitted effects."""
import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Any

from orket.core.contracts.interaction_context import flatten_packet1_context
from orket.core.contracts.interaction_stream import CommitIntent, StreamEventType


class InteractionContext:
    def __init__(
        self,
        *,
        session_id: str,
        turn_id: str,
        session_params: dict[str, Any],
        packet1_context_envelope: dict[str, Any],
        packet1_provider_lineage: list[dict[str, Any]],
        emit: Callable[[StreamEventType, dict[str, Any]], Awaitable[bool]],
        cancel_event: asyncio.Event,
        commit_sink: Callable[[CommitIntent], Awaitable[None]],
    ) -> None:
        self.session_id = session_id
        self.turn_id = turn_id
        self._session_params = deepcopy(session_params)
        self._packet1_context_envelope = deepcopy(packet1_context_envelope)
        self._packet1_provider_lineage = deepcopy(packet1_provider_lineage)
        self._emit = emit
        self._cancel_event = cancel_event
        self._commit_sink = commit_sink

    async def emit_event(self, event_type: StreamEventType, payload: dict[str, Any]) -> bool:
        return await self._emit(event_type, deepcopy(payload))

    async def request_commit(self, intent: CommitIntent) -> None:
        await self._commit_sink(intent.model_copy(deep=True))

    def session_params(self) -> dict[str, Any]:
        return deepcopy(self._session_params)

    def packet1_context(self) -> dict[str, Any]:
        return flatten_packet1_context(self._packet1_context_envelope)

    def packet1_context_envelope(self) -> dict[str, Any]:
        return deepcopy(self._packet1_context_envelope)

    def packet1_provider_lineage(self) -> list[dict[str, Any]]:
        return deepcopy(self._packet1_provider_lineage)

    def is_canceled(self) -> bool:
        return self._cancel_event.is_set()

    async def await_cancel(self) -> None:
        await self._cancel_event.wait()
