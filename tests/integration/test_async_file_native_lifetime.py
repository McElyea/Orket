"""Integration: admitted native file opens settle before the calling operation returns."""
import asyncio
import io
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiofiles.threadpool
import aiosqlite
import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_native_open(monkeypatch, target, state, *, failure):
    original = io.open

    def held(file, *args, **kwargs):
        stream = original(file, *args, **kwargs)
        if isinstance(file, int) or Path(file) != target or state.entered.is_set():
            return stream
        state.streams.append(stream)
        state.entered.set()
        try:
            assert state.release.wait(5), "Native open was not released"
            if failure:
                with original(target.parent / "absent-native-input", "rb"):
                    pass
            return stream
        except BaseException:
            stream.close()
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(io, "open", held)
    monkeypatch.setattr(aiofiles.threadpool, "sync_open", held)


async def observe_native_operation(adapter, operation, args, root, state, stop, layer, record_property):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await getattr(adapter, operation)(*args)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    pytest.fail(f"File operation returned before native admission: {await task}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
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
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        if stop == "failure" and layer == "family":
            assert (await asyncio.wait_for(task, 5))["ok"] is False
        else:
            expected = FileNotFoundError if stop == "failure" else TimeoutError if stop == "timeout" else asyncio.CancelledError
            with pytest.raises(expected):
                await asyncio.wait_for(task, 5)
        assert all(stream.closed for stream in state.streams)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)
        for stream in state.streams:
            await asyncio.to_thread(stream.close)
    assert not timer.is_alive()


@pytest.mark.parametrize("layer", ["adapter", "family"])
@pytest.mark.parametrize("operation", ["read_file", "write_file"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "failure"])
async def test_native_file_open_remains_owned(tmp_path, monkeypatch, record_property, layer, operation, stop):
    target = tmp_path / "target.txt"
    await asyncio.to_thread(target.write_text, "native input", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    hold_native_open(monkeypatch, target, state, failure=stop == "failure")
    adapter = AsyncFileTools(tmp_path) if layer == "adapter" else FileSystemTools(tmp_path, [])
    args = [target.name] if layer == "adapter" else [{"path": target.name}]
    if operation == "write_file":
        if layer == "adapter":
            args.append("native payload")
        else:
            args[0]["content"] = "native payload"
    await observe_native_operation(adapter, operation, args, tmp_path, state, stop, layer, record_property)
