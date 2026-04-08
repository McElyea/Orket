from __future__ import annotations

import asyncio

import pytest

from orket.streaming.bus import StreamBus, StreamBusConfig
from orket.streaming.contracts import StreamEventType


@pytest.mark.asyncio
async def test_bus_enforces_terminality_and_commit_final_order():
    bus = StreamBus()
    queue = await bus.subscribe("s1")
    ev0 = await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TURN_ACCEPTED, payload={})
    ev1 = await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TURN_FINAL, payload={})
    ev2 = await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.COMMIT_FINAL, payload={})
    assert ev0 is not None and ev1 is not None and ev2 is not None
    assert ev0.seq == 0
    assert ev1.seq == 1
    assert ev2.seq > ev1.seq
    with pytest.raises(ValueError):
        await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TOKEN_DELTA, payload={"delta": "x"})
    with pytest.raises(ValueError):
        await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.COMMIT_FINAL, payload={})
    # Drain queue to ensure events were broadcast.
    received = [await queue.get(), await queue.get(), await queue.get()]
    assert [item.event_type for item in received] == [
        StreamEventType.TURN_ACCEPTED,
        StreamEventType.TURN_FINAL,
        StreamEventType.COMMIT_FINAL,
    ]


@pytest.mark.asyncio
async def test_bus_emits_dropped_seq_ranges_for_best_effort_overflow():
    bus = StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=1,
            bounded_max_events_per_turn=10,
            max_bytes_per_turn_queue=100000,
        )
    )
    await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TOKEN_DELTA, payload={"delta": "a"})
    dropped = await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TOKEN_DELTA, payload={"delta": "b"})
    assert dropped is None
    final = await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TURN_FINAL, payload={})
    assert final is not None
    assert "dropped_seq_ranges" in final.payload
    assert final.payload["dropped_seq_ranges"] == [{"start_seq": 1, "end_seq": 1}]


@pytest.mark.asyncio
async def test_bus_subscriber_queue_is_bounded_to_producer_budget():
    """Layer: unit. Verifies subscriber queues cannot grow without a configured bound."""
    bus = StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=2,
            bounded_max_events_per_turn=3,
            max_bytes_per_turn_queue=100000,
        )
    )

    queue = await bus.subscribe("s1")

    assert queue.maxsize == 5


@pytest.mark.asyncio
async def test_bus_purge_turn_evicts_state_and_drains_matching_subscriber_events():
    """Layer: unit. Verifies explicit turn purge removes retained state and queued turn events."""
    bus = StreamBus()
    queue = await bus.subscribe("s1")
    await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TURN_ACCEPTED, payload={})
    await bus.publish(session_id="s1", turn_id="t2", event_type=StreamEventType.TURN_ACCEPTED, payload={})

    await bus.purge_turn("s1", "t1")

    assert ("s1", "t1") not in bus._turn_states
    assert (await queue.get()).turn_id == "t2"
    assert queue.empty()


@pytest.mark.asyncio
async def test_bus_emits_single_stream_truncated_event_for_best_effort_budget_exhaustion():
    """Layer: unit. Verifies producer budget exhaustion is visible to subscribers exactly once per turn."""
    bus = StreamBus()
    queue = await bus.subscribe("s1")

    for index in range(300):
        await bus.publish(
            session_id="s1",
            turn_id="t1",
            event_type=StreamEventType.TOKEN_DELTA,
            payload={"delta": str(index)},
        )

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    truncated = [event for event in events if event.event_type == StreamEventType.STREAM_TRUNCATED]

    assert len(truncated) == 1
    assert truncated[0].payload["dropped_seq_ranges"] == [{"start_seq": 256, "end_seq": 256}]


def test_bus_drain_queue_ignores_queuefull_when_requeueing_retained_events() -> None:
    """Layer: unit. Verifies turn purge stays best-effort when subscriber requeueing overflows."""

    class _Event:
        def __init__(self, session_id: str, turn_id: str) -> None:
            self.session_id = session_id
            self.turn_id = turn_id

    class _Queue:
        def __init__(self) -> None:
            self._events = [_Event("s1", "t1"), _Event("s1", "t2")]
            self.task_done_calls = 0

        def get_nowait(self) -> _Event:
            if not self._events:
                raise asyncio.QueueEmpty
            return self._events.pop(0)

        def task_done(self) -> None:
            self.task_done_calls += 1

        def put_nowait(self, _event: _Event) -> None:
            raise asyncio.QueueFull

    queue = _Queue()

    StreamBus._drain_queue_for_turn(queue, session_id="s1", turn_id="t1")

    assert queue.task_done_calls == 2


@pytest.mark.asyncio
async def test_bus_turn_budget_override_allows_higher_best_effort_volume_without_drop() -> None:
    """Layer: unit. Verifies per-turn stream-budget overrides can raise the best-effort event cap truthfully."""
    bus = StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=8,
            best_effort_max_events_per_turn_override=512,
            bounded_max_events_per_turn=16,
            max_bytes_per_turn_queue=1_000_000,
        )
    )
    queue = await bus.subscribe("s1")
    await bus.configure_turn_budget(session_id="s1", turn_id="t1", best_effort_max_events_per_turn=512)

    for index in range(300):
        await bus.publish(
            session_id="s1",
            turn_id="t1",
            event_type=StreamEventType.TOKEN_DELTA,
            payload={"delta": str(index)},
        )

    events = [queue.get_nowait() for _ in range(queue.qsize())]
    assert len(events) == 300
    assert all(event.event_type != StreamEventType.STREAM_TRUNCATED for event in events)


@pytest.mark.asyncio
async def test_bus_evicts_old_turn_state_entries_when_capacity_is_exceeded() -> None:
    """Layer: unit. Verifies retained turn-state bookkeeping is bounded by the configured LRU cap."""
    bus = StreamBus(
        StreamBusConfig(
            best_effort_max_events_per_turn=8,
            bounded_max_events_per_turn=8,
            max_bytes_per_turn_queue=100000,
            turn_state_max_entries=1,
        )
    )

    await bus.publish(session_id="s1", turn_id="t1", event_type=StreamEventType.TURN_ACCEPTED, payload={})
    assert ("s1", "t1") in bus._turn_states

    await bus.publish(session_id="s1", turn_id="t2", event_type=StreamEventType.TURN_ACCEPTED, payload={})

    assert ("s1", "t1") not in bus._turn_states
    assert ("s1", "t2") in bus._turn_states
