"""Controlled native latency around real runtime-verification filesystem work."""
import asyncio
import io
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiofiles.threadpool
import aiosqlite


def hold_path(monkeypatch, operation, selected, *, watchdog=5):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), thread=None, expired=False)
    original = getattr(Path, operation)

    def held(path, *args, **kwargs):
        if Path(path) == selected and not state.entered.is_set():
            state.thread = threading.get_ident()
            state.entered.set()
            try:
                state.expired = not state.release.wait(watchdog)
                return original(path, *args, **kwargs)
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, operation, held)
    return state


async def wait_entered(hold):
    assert await asyncio.to_thread(hold.entered.wait, 3), "native operation did not start"


async def sqlite_response(database, record_property, started=None):
    started = time.perf_counter() if started is None else started
    async with aiosqlite.connect(database) as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    elapsed = time.perf_counter() - started
    record_property("sqlite_response_seconds", elapsed)
    return elapsed


async def settle(task, hold):
    hold.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    if hold.entered.is_set():
        assert await asyncio.to_thread(hold.finished.wait, 3)


async def cancel_while_held(task, hold, database, record_property):
    await wait_entered(hold)
    task.cancel("first caller interruption")
    await asyncio.sleep(0)
    task.cancel("repeated caller interruption")
    elapsed = await sqlite_response(database, record_property)
    assert elapsed < 0.5
    await asyncio.sleep(0.02)
    assert not task.done(), "caller returned before native work settled"
    hold.release.set()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("interruption was lost")
    assert hold.finished.is_set()


def hold_stream(monkeypatch, selected, operation, *, failure=False):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), streams=[], thread=None)
    original_open = io.open

    def native_open(file, *args, **kwargs):
        stream = original_open(file, *args, **kwargs)
        if isinstance(file, int) or Path(file) != selected:
            return stream
        state.streams.append(stream)

        def held(original, *values, **options):
            if state.entered.is_set():
                return original(*values, **options)
            state.thread = threading.get_ident()
            state.entered.set()
            try:
                assert state.release.wait(5), "native stream operation was not released"
                result = original(*values, **options)
                if failure:
                    raise OSError("controlled native stream failure")
                return result
            finally:
                state.finished.set()

        if operation == "open":
            try:
                return held(lambda: stream)
            except BaseException:
                stream.close()
                raise
        original = getattr(stream, operation)
        setattr(stream, operation, lambda *values, **options: held(original, *values, **options))
        return stream

    monkeypatch.setattr(io, "open", native_open)
    monkeypatch.setattr(aiofiles.threadpool, "sync_open", native_open)
    return state


async def timeout_while_held(task, hold, database, record_property):
    await wait_entered(hold)
    waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
    try:
        await asyncio.sleep(0.04)
        assert not waiter.done() and not task.done(), "timeout escaped an admitted native operation"
        assert await sqlite_response(database, record_property) < 0.5
        hold.release.set()
        try:
            await waiter
        except TimeoutError:
            pass
        else:
            raise AssertionError("timeout was lost")
    finally:
        hold.release.set()
        await asyncio.gather(waiter, return_exceptions=True)
