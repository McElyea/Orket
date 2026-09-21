"""Native path resolution keeps its admitted root and worker through interruption."""
import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.interfaces.cli import _resolve_path

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_resolution(monkeypatch, root, *, failure=False):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), files=[])
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path not in {Path("chosen"), root / "chosen"}:
            return original(path, *args, **kwargs)
        try:
            with (root / "seed.bin").open("rb") as stream:
                state.files.append(stream)
                assert stream.read() == b"input"
                state.entered.set()
                assert state.release.wait(5), "Native resolution release deadline"
                if failure:
                    (root / "missing-resolution-input").read_bytes()
                return original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "resolve", resolve)
    return state


@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_runtime_path_resolution_is_owned(tmp_path, monkeypatch, record_property, stop):
    await asyncio.to_thread((tmp_path / "seed.bin").write_bytes, b"input")
    monkeypatch.chdir(tmp_path)
    state = hold_resolution(monkeypatch, tmp_path, failure=stop == "worker_failure")

    async def invoke():
        async with asyncio.timeout(.05 if stop == "timeout" else 5):
            return await _resolve_path("chosen")

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        async with aiosqlite.connect(tmp_path / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        if stop != "timeout":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not state.files[0].closed
        state.release.set()
        error = FileNotFoundError if stop == "worker_failure" else (
            TimeoutError if stop == "timeout" else asyncio.CancelledError)
        with pytest.raises(error):
            await asyncio.wait_for(task, 5)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
    assert state.finished.is_set() and not timer.is_alive() and all(stream.closed for stream in state.files)


async def test_runtime_path_resolution_captures_relative_root_before_worker(tmp_path, monkeypatch):
    await asyncio.to_thread((tmp_path / "seed.bin").write_bytes, b"input")
    foreign = tmp_path / "foreign"
    await asyncio.to_thread(foreign.mkdir)
    monkeypatch.chdir(tmp_path)
    state = hold_resolution(monkeypatch, tmp_path)
    task = asyncio.create_task(_resolve_path("chosen"))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        monkeypatch.chdir(foreign)
        state.release.set()
        assert await asyncio.wait_for(task, 5) == tmp_path / "chosen"
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert state.finished.is_set() and all(stream.closed for stream in state.files)
