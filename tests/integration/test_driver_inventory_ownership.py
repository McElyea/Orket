"""Actual driver inventory and asset listing must not block or abandon workers."""
import asyncio
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.driver import OrketDriver

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_inventory_read(monkeypatch, root, stage, failure):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), files=[])
    name = 'iterdir' if stage == 'inventory' else 'glob'
    original = getattr(Path, name)
    target = root / ('model' if stage == 'inventory' else 'model/core/epics')

    def held(path, *args, **kwargs):
        if path != target or state.entered.is_set():
            yield from original(path, *args, **kwargs)
            return
        try:
            with (root / 'model/core/environments/standard.json').open('rb') as stream:
                state.files.append(stream)
                state.entered.set()
                assert state.release.wait(5), 'Driver inventory release deadline'
                assert json.load(stream)['name'] == 'standard'
                if failure:
                    (root / 'missing-inventory-input.json').read_bytes()
                yield from original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, name, held)
    return state


@pytest.mark.parametrize('stage', ['inventory', 'assets'])
@pytest.mark.parametrize('stop', ['cancel', 'timeout', 'worker_failure'])
async def test_driver_inventory_worker_is_responsive_and_owned(test_root, workspace, monkeypatch, record_property, stage, stop):
    dispatch_release, calls = asyncio.Event(), []

    async def complete(messages):
        calls.append(messages)
        await dispatch_release.wait()
        return SimpleNamespace(content='{"action":"converse","response":"ok","reasoning":"fixture"}')

    provider = SimpleNamespace(model='qwen-test', complete=complete)
    driver = await asyncio.to_thread(OrketDriver, project_root=test_root, provider=provider, strict_config=False)
    state = hold_inventory_read(monkeypatch, test_root, stage, stop == 'worker_failure')

    async def invoke():
        async with asyncio.timeout(.05 if stop == 'timeout' else 5):
            return await driver.process_request('settings')

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    await task
                await asyncio.sleep(.001)
        async with aiosqlite.connect(workspace / 'responsive.sqlite3') as connection:
            assert await (await connection.execute('SELECT 42')).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < .5
        if stop != 'timeout':
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not state.finished.is_set() and not state.files[0].closed
        state.release.set()
        expected = FileNotFoundError if stop == 'worker_failure' else (TimeoutError if stop == 'timeout' else asyncio.CancelledError)
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
        assert not calls
    finally:
        state.release.set()
        dispatch_release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
    assert not timer.is_alive() and state.finished.is_set() and all(stream.closed for stream in state.files)
