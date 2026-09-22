"""Shared real-request/native-read lifetime assertions with a predeclared latency bound."""
import asyncio
import threading
import time

import aiosqlite
import pytest


async def _interrupt(app, request, stop):
    if stop in {"shutdown", "shutdown_cancel"}:
        closing = asyncio.create_task(app.state.api_runtime_context.close())
        if stop == "shutdown_cancel":
            await asyncio.sleep(.02)
            closing.cancel()
            await asyncio.sleep(0)
            closing.cancel()
        return closing
    if stop != "timeout":
        request.cancel()
        await asyncio.sleep(0)
        request.cancel()
    return None


async def _settle_close(app, closing, stop):
    if closing is None:
        return
    result, = await asyncio.gather(closing, return_exceptions=True)
    if stop == "shutdown_cancel":
        assert isinstance(result, asyncio.CancelledError)
    else:
        assert result is None
    assert app.state.api_runtime_context.closed


async def _settle_request(request, stop):
    if stop in {"shutdown", "shutdown_cancel"}:
        # The established ASGI contract translates shutdown cancellation to 503.
        assert (await asyncio.wait_for(request, 5)).status_code == 503
        return
    expected = OSError if stop == "worker_failure" else TimeoutError if stop == "timeout" else asyncio.CancelledError
    with pytest.raises(expected):
        await asyncio.wait_for(request, 5)


async def exercise_owned_api_read(app, client, route, state, tmp_path, record_property, stop):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await client.get(route)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    request = asyncio.create_task(invoke())
    closing = None
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if request.done():
                    pytest.fail(f"Request ended before native read: {await request}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
        async with aiosqlite.connect(tmp_path / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        assert (await client.get("/v1/system/heartbeat")).status_code == 200
        closing = await _interrupt(app, request, stop)
        await asyncio.sleep(.08)
        assert not request.done() and not state.finished.is_set() and not state.files[0].closed
        assert app.state.api_runtime_context.active_request_count == 1
        if closing is not None:
            assert not closing.done() and not app.state.api_runtime_context.closed
        state.release.set()
        await _settle_request(request, stop)
        await _settle_close(app, closing, stop)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(request, *([closing] if closing is not None else []), return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)
    assert not timer.is_alive() and all(stream.closed for stream in state.files)
    assert app.state.api_runtime_context.active_request_count == 0
