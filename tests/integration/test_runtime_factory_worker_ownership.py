"""Actual runtime factories must remain responsive and retain acquired owners."""
from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

import orket.runtime.execution.execution_pipeline as pipeline_module
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.application.services.runtime_result_lifetime import execute_collection_member
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def held_runtime_factory(test_root, workspace, db_path):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            owners=[], files=[], dispatched=False, dispatch_release=asyncio.Event())
    original = pipeline_module.ExecutionPipeline

    def construct(*args, **kwargs):
        kwargs.update(config_root=test_root, db_path=db_path)
        owner = original(*args, **kwargs)
        state.owners.append(owner)

        async def forbidden_dispatch(*_args, **_kwargs):
            state.dispatched = True
            await state.dispatch_release.wait()
            raise AssertionError('Interrupted construction must not dispatch')

        owner.run_card = forbidden_dispatch
        try:
            with (test_root / 'model/core/epics/publication_epic.json').open('rb') as stream:
                state.files.append(stream)
                state.entered.set()
                assert state.release.wait(5), 'Native factory release deadline'
        finally:
            state.finished.set()
        return owner

    return state, construct


@pytest.mark.parametrize('route', ['public', 'collection'])
@pytest.mark.parametrize('interrupt', ['cancel', 'timeout'])
async def test_runtime_factory_worker_is_owned(test_root, workspace, db_path, monkeypatch, record_property, route, interrupt):
    await asyncio.to_thread(_write_epic_assets, test_root, 'publication_epic')
    state, construct = held_runtime_factory(test_root, workspace, db_path)
    monkeypatch.setattr(pipeline_module, 'ExecutionPipeline', construct)

    async def invoke():
        async with asyncio.timeout(.05 if interrupt == 'timeout' else 5):
            if route == 'public':
                return await pipeline_module.orchestrate_card('publication_epic', workspace,
                    session_id='factory-session', build_id='factory-build')
            return await execute_collection_member(create=construct, creation={'workspace': workspace},
                target='publication_epic', session_id='factory-session', build_id='factory-build', execution={})

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
        assert not task.done() and not state.finished.is_set() and not state.files[0].closed
        state.release.set()
        expected = RuntimeExecutionCancelled if route == 'collection' else (
            TimeoutError if interrupt == 'timeout' else asyncio.CancelledError)
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
        assert not state.dispatched and all(owner._closed for owner in state.owners)
    finally:
        state.release.set()
        state.dispatch_release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        for owner in state.owners:
            await owner.close()
    assert state.finished.is_set() and all(stream.closed for stream in state.files) and not timer.is_alive()
