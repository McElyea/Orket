"""Real bounded subscriber queues must release publishers when detached."""
import asyncio

import pytest

from orket.core.contracts.interaction_stream import StreamEventType
from orket.streaming.bus import StreamBus, StreamBusConfig

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_detaching_full_subscriber_releases_its_pending_publication():
    bus = StreamBus(StreamBusConfig(best_effort_max_events_per_turn=1, bounded_max_events_per_turn=0))
    queue = await bus.subscribe("session")
    await bus.publish(session_id="session", turn_id="turn", event_type=StreamEventType.TURN_ACCEPTED)
    publisher = asyncio.create_task(bus.publish(session_id="session", turn_id="turn", event_type=StreamEventType.TOKEN_DELTA))
    try:
        await asyncio.sleep(0.02)
        assert queue.full() and not publisher.done()
        await bus.unsubscribe("session", queue)
        await asyncio.wait_for(asyncio.shield(publisher), 0.5)
        assert "session" not in bus._subscribers
    finally:
        # The adverse run must also release the actual blocked queue operation.
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()
        await asyncio.wait_for(asyncio.gather(publisher, return_exceptions=True), 3)
        await bus.unsubscribe("session", queue)
