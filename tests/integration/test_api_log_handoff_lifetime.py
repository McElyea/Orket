"""Layer: integration. API close retains captured real log handoff attempts."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from contextlib import AsyncExitStack

import pytest

from orket.application.services.api_event_service import ApiEventService
from orket.interfaces.api import create_api_app
from orket.logging import event_subscriber_count
from tests.helpers.logging_async_opening import sqlite_observation

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
EVENT = "api_retained_log_handoff"


async def _app(stack, root):
    app = create_api_app(project_root=root, environment={**os.environ, "ORKET_API_KEY": "fixture-key"})
    await stack.enter_async_context(app.router.lifespan_context(app))
    return app.state.api_runtime_context


def _hold_handoff(loop, monkeypatch):
    original = loop.call_soon_threadsafe
    entered = threading.Event()
    captured = []

    def hold(callback, *args, **kwargs):
        if args and type(args[0]) is dict and args[0].get("event") == EVENT:
            captured.append((callback, args, kwargs))
            entered.set()
            return None
        return original(callback, *args, **kwargs)

    monkeypatch.setattr(loop, "call_soon_threadsafe", hold)

    def release():
        while captured:
            callback, args, kwargs = captured.pop(0)
            original(callback, *args, **kwargs)

    return entered, captured, release


def _observe_queue(monkeypatch, owner):
    queue = owner.runtime_state.event_queue
    original = queue.put_nowait
    attempts = []

    def put(record):
        if record.get("event") in {EVENT, "peer_after_cutoff"}:
            attempts.append((record["event"], owner.closed))
        return original(record)

    monkeypatch.setattr(queue, "put_nowait", put)
    return attempts


async def _wait_for(predicate):
    async with asyncio.timeout(3):
        while not predicate():  # noqa: ASYNC110 - observe production lifecycle state without replacing it
            await asyncio.sleep(0.005)


async def _close(owner, stop):
    if stop == "timeout":
        async with asyncio.timeout(0.05):
            await owner.close()
    else:
        await owner.close()


@pytest.mark.parametrize("stop", ["close", "cancel", "timeout", "peer"])
async def test_api_close_retains_captured_event_queue_handoff(tmp_path, monkeypatch, record_property, stop):
    baseline = event_subscriber_count()
    loop = asyncio.get_running_loop()
    async with AsyncExitStack() as stack:
        owner = await _app(stack, tmp_path / "first")
        attempts = _observe_queue(monkeypatch, owner)
        entered, captured, release = _hold_handoff(loop, monkeypatch)
        await ApiEventService(tmp_path / "publisher").emit(EVENT, {"captured": True})
        assert entered.is_set() and len(captured) == 1
        peer = await _app(stack, tmp_path / "peer") if stop == "peer" else None
        peer_attempts = _observe_queue(monkeypatch, peer) if peer is not None else []
        closing = asyncio.create_task(_close(owner, stop))
        try:
            await _wait_for(lambda: not owner.accepting_work)
            if stop == "cancel":
                closing.cancel()
                await asyncio.sleep(0)
                closing.cancel()
            await asyncio.sleep(0.10)
            pending = not closing.done() and not owner.closed
            retained_count = event_subscriber_count()
            sqlite = await sqlite_observation(tmp_path / f"{stop}.sqlite3", time.perf_counter())
            if peer is not None:
                await ApiEventService(tmp_path / "publisher").emit("peer_after_cutoff", {})
                await _wait_for(lambda: bool(peer_attempts))
            release()
            result, = await asyncio.wait_for(asyncio.gather(closing, return_exceptions=True), 3)
            await asyncio.sleep(0)
        finally:
            release()
            await asyncio.wait_for(asyncio.gather(closing, return_exceptions=True), 3)
        after_count = event_subscriber_count()
        path = tmp_path / "publisher" / "orket.log"
        records = [json.loads(line) for line in (await asyncio.to_thread(path.read_text, encoding="utf-8")).splitlines()]
        observation = dict(stop=stop, pending_before_release=pending, baseline=baseline,
            retained_count=retained_count, after_count=after_count, captured_callbacks=1,
            attempts=attempts, peer_attempts=peer_attempts, sqlite=sqlite, closed=owner.closed,
            result_type=type(result).__name__, path=str(path), records=records, captured_remaining=len(captured))
        record_property("api_log_handoff", json.dumps(observation, sort_keys=True))
        assert pending, "API close escaped before a captured loop handoff attempted"
        assert retained_count == baseline + 1 + int(peer is not None)
        assert after_count == baseline + int(peer is not None)
        assert attempts == [(EVENT, False)] and not captured and owner.closed
        assert sqlite["row"] == (42,) and 0 < sqlite["elapsed"] < 0.5
        assert records[0]["event"] == EVENT and records[0]["data"]["captured"] is True
        if stop == "cancel":
            assert isinstance(result, asyncio.CancelledError)
        elif stop == "timeout":
            assert isinstance(result, TimeoutError)
        else:
            assert result is None
        if peer is not None:
            assert peer_attempts == [("peer_after_cutoff", False)] and not peer.closed
    assert event_subscriber_count() == baseline
