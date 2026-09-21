"""Real organization assets and worker interruption at the loop boundary."""
import asyncio
import json
import threading
import time

import aiosqlite
import pytest

import orket.organization_loop as loop_module
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_runtime_factory_worker_ownership import held_runtime_factory

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def seed_organization(root):
    _write_epic_assets(root, 'publication_epic')
    path = root / 'config/organization.json'
    path.write_text(json.dumps({'name': 'owned', 'vision': 'test', 'ethos': 'test', 'departments': ['core']}), encoding='utf-8')


async def test_organization_scan_finds_authored_ready_card(test_root, monkeypatch):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    owner = await asyncio.to_thread(loop_module.OrganizationLoop)
    observed = await asyncio.to_thread(owner._find_next_critical_card)
    assert observed == {'id': 'ISSUE-1', 'weight': 1, 'priority': '3.0', 'dept': 'core'}


@pytest.mark.parametrize('interrupt', ['cancel', 'timeout'])
@pytest.mark.parametrize('failure', [False, True])
async def test_organization_scan_retains_native_worker(test_root, monkeypatch, interrupt, failure):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    owner = await asyncio.to_thread(loop_module.OrganizationLoop)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    files = []

    def scan():
        try:
            with (test_root / 'model/core/epics/publication_epic.json').open('rb') as stream:
                files.append(stream)
                entered.set()
                assert release.wait(5), 'Scan release deadline'
                assert json.load(stream)['id'] == 'publication_epic'
            if failure:
                (test_root / 'missing-after-scan.json').read_bytes()
            return None
        finally:
            finished.set()

    monkeypatch.setattr(owner, '_find_next_critical_card', scan)

    async def invoke():
        async with asyncio.timeout(.05 if interrupt == 'timeout' else 5):
            await owner.run_forever()

    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(entered.wait, 3)
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
        assert await asyncio.to_thread(finished.wait, 5)
    assert all(stream.closed for stream in files)


@pytest.mark.parametrize('interrupt', ['cancel', 'timeout'])
async def test_organization_runtime_factory_is_owned(test_root, workspace, db_path, monkeypatch, record_property, interrupt):
    await asyncio.to_thread(seed_organization, test_root)
    monkeypatch.chdir(test_root)
    owner = await asyncio.to_thread(loop_module.OrganizationLoop)
    state, construct = held_runtime_factory(test_root, workspace, db_path)
    monkeypatch.setattr(loop_module, 'ExecutionPipeline', construct)
    monkeypatch.setattr(owner, '_find_next_critical_card', lambda: {'id': 'ISSUE-1', 'dept': 'core'})

    async def invoke():
        async with asyncio.timeout(.05 if interrupt == 'timeout' else 5):
            await owner.run_forever()

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
        if interrupt == 'cancel':
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not state.files[0].closed
        state.release.set()
        with pytest.raises(TimeoutError if interrupt == 'timeout' else asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert not state.dispatched and all(runtime._closed for runtime in state.owners)
    finally:
        state.release.set()
        state.dispatch_release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        for runtime in state.owners:
            await runtime.close()
    assert not timer.is_alive() and state.finished.is_set() and all(stream.closed for stream in state.files)
