"""Real SQLite close work stays owned and leaves the event loop responsive."""
import asyncio
import sqlite3
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

from tests.helpers.runtime_cleanup_ports import (
    AsyncCleanupPort,
    NativeCleanupPort,
    create_cleanup_runtime,
    exception_leaves,
    release_cleanup_runtime,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def interrupt_cleanup(owner, ports, hold, root, stop, record_property):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            hold.deadline = deadline
            await owner.close()

    timer = threading.Timer(.8, hold.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not hold.entered.is_set():
                if task.done():
                    pytest.fail(f"Cleanup returned before native admission: {await task}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            hold.deadline.reschedule(asyncio.get_running_loop().time() + .05)
        async with aiosqlite.connect(root / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        if stop != "timeout":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not any(port.closed for port in ports)
        hold.release.set()
        expected = (sqlite3.OperationalError, ExceptionGroup) if stop == "failure" else (
            TimeoutError if stop == "timeout" else asyncio.CancelledError)
        with pytest.raises(expected) as caught:
            await asyncio.wait_for(task, 5)
        if stop == "failure":
            assert all(isinstance(error, sqlite3.OperationalError) for error in exception_leaves(caught.value))
        for index, port in enumerate(ports):
            assert await asyncio.to_thread(port.observe_closed) is not (index == 0 and stop == "failure")
    finally:
        hold.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
    assert not timer.is_alive()


@pytest.mark.parametrize("kind", ["engine", "pipeline", "context"])
@pytest.mark.parametrize("port_type", [NativeCleanupPort, AsyncCleanupPort], ids=["sync", "async"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "failure"])
async def test_runtime_close_owns_native_work(tmp_path, monkeypatch, record_property, kind, port_type, stop):
    monkeypatch.chdir(tmp_path)
    hold = SimpleNamespace(entered=threading.Event(), release=threading.Event())
    ports = [await asyncio.to_thread(port_type, tmp_path / f"resource-{index}.sqlite3",
        failure=index == 0 and stop == "failure", hold=hold if index == 0 else None) for index in range(4)]
    runtime = None
    try:
        runtime, owner = await create_cleanup_runtime(tmp_path, kind, ports)
        await interrupt_cleanup(owner, ports, hold, tmp_path, stop, record_property)
    finally:
        await release_cleanup_runtime(runtime, ports)
