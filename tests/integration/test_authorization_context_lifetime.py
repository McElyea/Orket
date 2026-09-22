"""Integration: authorization observation owns admitted native work through interruption."""
import asyncio
import threading
import time
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_connector_service import OutwardConnectorPolicyError, OutwardConnectorService

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("connector", ["read_file", "http_get", "run_command"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "failure"])
async def test_authorization_observation_retains_native_worker(tmp_path, monkeypatch, record_property, connector, stop):
    service = OutwardConnectorService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
        workspace_root=tmp_path, http_allowlist=("example.invalid",))
    args = {"read_file": {"path": "allowed.txt"}, "http_get": {"url": "https://example.invalid/proof"},
            "run_command": {"command": ["not-executed"]}}[connector]
    target = tmp_path / "allowed.txt" if connector == "read_file" else tmp_path
    entered, released, finished = threading.Event(), threading.Event(), threading.Event()
    original = Path.resolve

    def held(path, *args, **kwargs):
        if path != target or entered.is_set():
            return original(path, *args, **kwargs)
        entered.set()
        try:
            assert released.wait(5), "Authorization observation fixture was not released"
            if stop == "failure":
                (tmp_path / "absent-native-observation").read_bytes()
            return original(path, *args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Path, "resolve", held)
    deadlines = []

    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            deadlines.append(deadline)
            return await service.authorization_context(connector, args)

    timer = threading.Timer(.8, released.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not entered.is_set():
                if task.done():
                    pytest.fail(f"No native authorization observation: {await task}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            deadlines[0].reschedule(asyncio.get_running_loop().time() + .05)
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
        assert not task.done() and not finished.is_set()
        released.set()
        expected = asyncio.CancelledError if stop == "cancel" else TimeoutError
        if stop == "failure":
            expected = OutwardConnectorPolicyError if connector == "read_file" else FileNotFoundError
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
    finally:
        released.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(finished.wait, 5)
    assert not timer.is_alive()
