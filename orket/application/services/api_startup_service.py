"""Application-owned API initialization, event subscription and background admission."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.observability.log_publication import (
    begin_event_subscription_drain,
    settle_event_subscription,
    subscribe_to_event_handoffs,
)
from orket.application.services.api_runtime_container import ApiRuntimeContainer

LOGGER = logging.getLogger(__name__)


class _EventSubscription:
    def __init__(self, state: Any) -> None:
        loop = asyncio.get_running_loop()

        def enqueue(record: dict[str, Any], acknowledge: Callable[[], None]) -> None:
            try:
                state.event_queue.put_nowait(record)
            finally:
                acknowledge()

        def on_record(record: dict[str, Any], acknowledge: Callable[[], None]) -> None:
            loop.call_soon_threadsafe(enqueue, record, acknowledge)

        self.registration = subscribe_to_event_handoffs(on_record)

    async def aclose(self) -> None:
        begin_event_subscription_drain(self.registration)
        await run_owned_thread(partial(settle_event_subscription, self.registration), label="api-event-subscription-drain")


def _validate_root(configured_root: Path, owned_root: Path) -> None:
    if Path(configured_root).resolve() != owned_root:
        raise RuntimeError("API app runtime context does not match its configured project root.")


@asynccontextmanager
async def api_runtime_lifespan(
    owner: ApiRuntimeContainer, configured_root: Path, broadcaster: Callable[[], Awaitable[None]],
) -> AsyncIterator[None]:
    # Capture selected owners before startup can await or another caller can close.
    root, engine, authentication = owner.project_root, owner.engine, owner.authentication
    state, governed_runtime, events = owner.runtime_state, owner.governed_agent_runtime, owner.events

    async def initialize() -> None:
        await run_owned_thread(lambda: _validate_root(configured_root, root), label="api-startup-root")
        authentication.validate_startup(LOGGER)
        initialize_engine = getattr(engine, "initialize", None)
        if callable(initialize_engine):
            await initialize_engine()
        subscription = _EventSubscription(state)
        owner.register_owned_resource(subscription)
        owner.start_background(broadcaster)
        if governed_runtime is not None:
            await governed_runtime.start(owner)
        bypass_active = authentication.authenticate(None)
        await events.emit("api_security_posture", {
            "api_key_configured": authentication.key_configured,
            "insecure_no_api_key_bypass": bypass_active,
        })
        if bypass_active:
            await events.emit("api_security_warning", {
                "message": "ORKET_ALLOW_INSECURE_NO_API_KEY bypasses /v1 auth without ORKET_API_KEY.",
            })

    try:
        # Initialization uses the same admitted-invocation lifetime as requests;
        # close cancels and drains it before releasing any initialized resources.
        await owner.run_request(initialize)
        yield
    finally:
        await owner.close()
