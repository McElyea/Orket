"""Async organization construction retains its actual native read through interruption."""
import asyncio
import threading
import time

import aiosqlite
import pytest

import orket.organization_loop as loop_module
from tests.integration.test_organization_loop_ownership import seed_organization

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('interrupt', ['cancel', 'timeout'])
@pytest.mark.parametrize('failure', [False, True])
async def test_organization_create_owns_config_read(test_root, workspace, monkeypatch, record_property, interrupt, failure):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    files = []
    original = loop_module.AsyncFileTools.read_file_sync

    def read(owner, path):
        try:
            with (test_root / 'config/organization.json').open('rb') as stream:
                files.append(stream)
                entered.set()
                assert release.wait(5), 'Organization read deadline'
            if failure:
                (test_root / 'missing-organization.json').read_bytes()
            return original(owner, path)
        finally:
            finished.set()

    async def invoke():
        async with asyncio.timeout(.05 if interrupt == 'timeout' else 5):
            return await loop_module.OrganizationLoop.create()

    monkeypatch.setattr(loop_module.AsyncFileTools, 'read_file_sync', read)
    task = asyncio.create_task(invoke())
    started = time.perf_counter()
    try:
        async with asyncio.timeout(5):
            while not entered.is_set():
                if task.done():
                    await task
                await asyncio.sleep(.001)
        async with aiosqlite.connect(workspace / 'responsive.sqlite3') as connection:
            assert await (await connection.execute('SELECT 42')).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property('responsive_sqlite_seconds', elapsed)
        assert elapsed < .5
        if interrupt == 'cancel':
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not finished.is_set() and not files[0].closed
        release.set()
        expected = FileNotFoundError if failure else (TimeoutError if interrupt == 'timeout' else asyncio.CancelledError)
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    assert finished.is_set() and all(stream.closed for stream in files)
