"""Layer: integration. Metadata and receipt resources remain owned through interruption."""
import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.terraform_review.artifacts import write_artifact_bundle
from orket.runtime.execution.phase_c_runtime_truth import (
    SOURCE_ATTRIBUTION_RECEIPT_PATH,
    collect_source_attribution_facts,
)
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_async_file_native_lifetime import hold_native_open

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def held_metadata(monkeypatch, target, method, failure):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), threads=[])
    original = getattr(Path, method)

    def observe(path, *args, **options):
        if path != target or state.entered.is_set():
            return original(path, *args, **options)
        state.threads.append(threading.get_ident())
        state.entered.set()
        try:
            assert state.release.wait(5), 'Metadata fixture was not released'
            result = original(path, *args, **options)
            if failure:
                raise OSError('controlled native metadata failure')
            return result
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, method, observe)
    return state


@pytest.mark.parametrize('kind', ['artifact', 'attribution'])
@pytest.mark.parametrize('stop', ['cancel', 'timeout', 'native-failure'])
async def test_metadata_owner_retains_interrupted_native_work(tmp_path, monkeypatch, record_property, kind, stop):
    workspace = tmp_path / 'workspace'
    target = (workspace / 'terraform_plan_reviews/fixture/alpha.json' if kind == 'artifact'
              else workspace / SOURCE_ATTRIBUTION_RECEIPT_PATH)
    state = held_metadata(monkeypatch, target, 'resolve' if kind == 'artifact' else 'exists', stop == 'native-failure')
    deadline = asyncio.timeout(None)

    async def operation():
        async with deadline:
            if kind == 'artifact':
                return await write_artifact_bundle(workspace=workspace, execution_trace_ref='fixture', payloads={'alpha': {'value': 42}})
            return await collect_source_attribution_facts(workspace=workspace)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
        if stop == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        expected = OSError if stop == 'native-failure' else TimeoutError if stop == 'timeout' else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        assert not await asyncio.to_thread(target.exists)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert not timer.is_alive() and state.finished.is_set()


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
async def test_source_receipt_read_closes_before_interrupted_return(tmp_path, monkeypatch, record_property, stop):
    target = tmp_path / SOURCE_ATTRIBUTION_RECEIPT_PATH
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    await asyncio.to_thread(target.write_text, json.dumps({'claims': [], 'sources': []}), encoding='utf-8')
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    hold_native_open(monkeypatch, target, state, failure=False)
    deadline = asyncio.timeout(None)

    async def operation():
        async with deadline:
            return await collect_source_attribution_facts(workspace=tmp_path, policy={'source_attribution_mode': 'required'})

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
        if stop == 'timeout':
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        with pytest.raises(TimeoutError if stop == 'timeout' else asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set() and state.streams and all(stream.closed for stream in state.streams)
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert await asyncio.to_thread(state.finished.wait, 5)
        for stream in state.streams:
            await asyncio.to_thread(stream.close)
        assert not timer.is_alive()
