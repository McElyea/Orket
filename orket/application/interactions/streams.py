"""Application-owned subscription lifetime for interaction transports."""
from contextlib import asynccontextmanager

from orket.adapters.execution.owned_io import run_owned_io
from orket.streaming.bus import StreamBus


class InteractionStreams:
    def __init__(self, bus: StreamBus):
        self._bus = bus

    @asynccontextmanager
    async def subscribe(self, session_id: str):
        queue = await self._bus.subscribe(session_id)
        try:
            yield queue
        finally:
            await run_owned_io(lambda: self._bus.unsubscribe(session_id, queue),
                               label="interaction-unsubscribe", preserve_failure=True)
