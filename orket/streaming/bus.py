from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    BEST_EFFORT_EVENTS,
    BOUNDED_EVENTS,
    EventClass,
    StreamEvent,
    StreamEventType,
    event_class,
    mono_ts_ms_now,
    wall_ts_now_iso,
)


@dataclass
class _TurnBusState:
    next_seq: int = 0
    terminal_emitted: bool = False
    commit_final_emitted: bool = False
    stream_truncated_emitted: bool = False
    pending_dropped_ranges: list[tuple[int, int]] = field(default_factory=list)
    best_effort_count: int = 0
    bounded_count: int = 0
    bytes_count: int = 0


@dataclass
class StreamBusConfig:
    best_effort_max_events_per_turn: int = 256
    bounded_max_events_per_turn: int = 128
    max_bytes_per_turn_queue: int = 1_000_000


class StreamBus:
    def __init__(self, config: StreamBusConfig | None = None) -> None:
        self.config = config or StreamBusConfig()
        self._subscribers: dict[str, set[asyncio.Queue[StreamEvent]]] = defaultdict(set)
        self._turn_states: dict[tuple[str, str], _TurnBusState] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[StreamEvent]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=self._subscriber_queue_maxsize())
        async with self._lock:
            self._subscribers[session_id].add(queue)
        return queue

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[StreamEvent]) -> None:
        async with self._lock:
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(queue)
                if not self._subscribers[session_id]:
                    self._subscribers.pop(session_id, None)

    async def publish(
        self,
        *,
        session_id: str,
        turn_id: str,
        event_type: StreamEventType,
        payload: dict[str, Any] | None = None,
    ) -> StreamEvent | None:
        payload = dict(payload or {})
        state_key = (session_id, turn_id)
        event: StreamEvent | None = None
        advisory_event: StreamEvent | None = None
        subscribers: list[asyncio.Queue[StreamEvent]] = []

        async with self._lock:
            state = self._turn_states.setdefault(state_key, _TurnBusState())

            if state.terminal_emitted and event_type != StreamEventType.COMMIT_FINAL:
                raise ValueError("Post-terminal events are forbidden except commit_final")
            if state.commit_final_emitted and event_type == StreamEventType.COMMIT_FINAL:
                raise ValueError("commit_final has already been emitted for this turn")

            cls = event_class(event_type)
            event_bytes = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
            dropped = False
            dropped_seq = state.next_seq
            budget_exempt = event_type == StreamEventType.STREAM_TRUNCATED

            if cls == EventClass.BEST_EFFORT:
                if (
                    state.best_effort_count >= self.config.best_effort_max_events_per_turn
                    or (state.bytes_count + event_bytes) > self.config.max_bytes_per_turn_queue
                ):
                    dropped = True
            elif cls == EventClass.BOUNDED and (
                    state.bounded_count >= self.config.bounded_max_events_per_turn
                    or (state.bytes_count + event_bytes) > self.config.max_bytes_per_turn_queue
                ):
                    raise RuntimeError("bounded event queue capacity exceeded")

            if dropped:
                state.next_seq += 1
                self._append_drop_range(state.pending_dropped_ranges, dropped_seq, dropped_seq)
                subscribers = list(self._subscribers.get(session_id, set()))
                if subscribers and not state.stream_truncated_emitted:
                    state.stream_truncated_emitted = True
                    advisory_event = self._build_event_locked(
                        state=state,
                        session_id=session_id,
                        turn_id=turn_id,
                        event_type=StreamEventType.STREAM_TRUNCATED,
                        payload={
                            "authoritative": False,
                            "dropped_event_type": event_type.value,
                            "reason": "producer_budget_exhausted",
                        },
                    )
            else:
                if event_type == StreamEventType.STREAM_TRUNCATED:
                    if state.stream_truncated_emitted:
                        return None
                    state.stream_truncated_emitted = True
                event = self._build_event_locked(
                    state=state,
                    session_id=session_id,
                    turn_id=turn_id,
                    event_type=event_type,
                    payload=payload,
                )

            if event is not None and event_type in BEST_EFFORT_EVENTS:
                state.best_effort_count += 1
            elif event is not None and event_type in BOUNDED_EVENTS and not budget_exempt:
                state.bounded_count += 1
            if event is not None and not budget_exempt:
                state.bytes_count += event_bytes

            if event is not None and event_type in {StreamEventType.TURN_INTERRUPTED, StreamEventType.TURN_FINAL}:
                state.terminal_emitted = True
            if event is not None and event_type == StreamEventType.COMMIT_FINAL:
                state.commit_final_emitted = True

            if event is not None:
                subscribers = list(self._subscribers.get(session_id, set()))

        outgoing_event = advisory_event or event
        if outgoing_event is not None:
            for queue in subscribers:
                await queue.put(outgoing_event)
        return event

    async def purge_turn(self, session_id: str, turn_id: str, *, drain_subscriber_queues: bool = True) -> None:
        async with self._lock:
            self._turn_states.pop((session_id, turn_id), None)
            if drain_subscriber_queues:
                for queue in list(self._subscribers.get(session_id, set())):
                    self._drain_queue_for_turn(queue, session_id=session_id, turn_id=turn_id)

    async def clear_turn(self, session_id: str, turn_id: str) -> None:
        await self.purge_turn(session_id, turn_id)

    def _subscriber_queue_maxsize(self) -> int:
        return max(
            1,
            self.config.best_effort_max_events_per_turn + self.config.bounded_max_events_per_turn,
        )

    @staticmethod
    def _drain_queue_for_turn(
        queue: asyncio.Queue[StreamEvent],
        *,
        session_id: str,
        turn_id: str,
    ) -> None:
        retained: list[StreamEvent] = []
        while True:
            try:
                event = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            queue.task_done()
            if event.session_id != session_id or event.turn_id != turn_id:
                retained.append(event)
        for event in retained:
            queue.put_nowait(event)

    @staticmethod
    def _build_event_locked(
        *,
        state: _TurnBusState,
        session_id: str,
        turn_id: str,
        event_type: StreamEventType,
        payload: dict[str, Any],
    ) -> StreamEvent:
        seq = state.next_seq
        state.next_seq += 1
        payload_out = dict(payload)
        if state.pending_dropped_ranges:
            payload_out["dropped_seq_ranges"] = [
                {"start_seq": start, "end_seq": end} for start, end in state.pending_dropped_ranges
            ]
            state.pending_dropped_ranges.clear()
        return StreamEvent(
            session_id=session_id,
            turn_id=turn_id,
            seq=seq,
            mono_ts_ms=mono_ts_ms_now(),
            wall_ts=wall_ts_now_iso(),
            event_type=event_type,
            payload=payload_out,
        )

    @staticmethod
    def _append_drop_range(ranges: list[tuple[int, int]], start: int, end: int) -> None:
        if not ranges:
            ranges.append((start, end))
            return
        prev_start, prev_end = ranges[-1]
        if start <= (prev_end + 1):
            ranges[-1] = (prev_start, max(prev_end, end))
            return
        ranges.append((start, end))
