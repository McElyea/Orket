"""A synchronous loader call must not hold the event loop behind native file work."""
import asyncio
import threading
import time
from functools import partial

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.runtime.config.config_loader import ConfigLoader

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_config_sync_refusal_preserves_sqlite_responsiveness(tmp_path, monkeypatch, record_property):
    await asyncio.to_thread((tmp_path / "input.txt").write_text, "owned", encoding="utf-8")
    loader = await run_owned_thread(partial(ConfigLoader, tmp_path), label="config-responsiveness-fixture")
    entered, release = threading.Event(), threading.Event()
    streams = []

    def read_native():
        with (tmp_path / "input.txt").open(encoding="utf-8") as stream:
            streams.append(stream)
            assert stream.read() == "owned"
            entered.set()
            assert release.wait(5), "Config worker release deadline"

    async def read_async():
        return await run_owned_thread(read_native, label="config-native-read-fixture")

    monkeypatch.setattr(loader, "load_organization_async", read_async)
    timer = threading.Timer(.8, release.set)
    timer.start()
    started, error = time.perf_counter(), None
    try:
        try:
            loader.load_organization()
        except RuntimeError as exc:
            error = exc
        async with aiosqlite.connect(tmp_path / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        assert error is not None and str(error) == "E_CONFIG_LOADER_REQUIRES_ASYNC_METHOD"
        assert not entered.is_set()
    finally:
        release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
    assert not timer.is_alive() and all(stream.closed for stream in streams)
