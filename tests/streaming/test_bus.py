from __future__ import annotations

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
