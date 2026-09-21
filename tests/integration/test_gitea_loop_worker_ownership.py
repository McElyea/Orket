"""Actual clients/files/SQLite under held workers; ready-queue responses are controlled."""
import asyncio
import json
import threading

import pytest

import orket.application.services.gitea_state_worker_coordinator as coordinator_module
import orket.runtime.execution.gitea_state_loop as loop_module
from orket.adapters.storage.async_file_tools import AsyncFileTools
from tests.helpers.gitea_loop_inputs import assert_sqlite_response, local_runner, probe_database

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('stage', ['construction', 'summary'])
@pytest.mark.parametrize('interruption', ['cancel', 'timeout', 'worker_failure'])
async def test_gitea_worker_retains_io_and_transport(tmp_path, monkeypatch, record_property, stage, interruption):
    runner, clients, _adapter_type = local_runner(tmp_path, monkeypatch)
    files = AsyncFileTools(tmp_path)
    await files.write_file('held-resource.txt', 'owned')
    database = await probe_database(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    handles = []
    original = loop_module.GiteaStateWorker if stage == 'construction' else coordinator_module._write_summary

    def held_operation(*args, **kwargs):
        try:
            with (tmp_path / 'held-resource.txt').open(encoding='utf-8') as handle:
                handles.append(handle)
                assert handle.read() == 'owned'
                entered.set()
                assert release.wait(5), 'Gitea worker was not released'
                if interruption == 'worker_failure':
                    raise OSError('controlled-worker-failure')
                return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(loop_module if stage == 'construction' else coordinator_module,
        'GiteaStateWorker' if stage == 'construction' else '_write_summary', held_operation)
    operation = asyncio.create_task(runner.run(worker_id='owned-worker', max_idle_streak=1, summary_out='summary.json'))
    waiter = operation
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await assert_sqlite_response(database, record_property)
        if interruption == 'timeout':
            waiter = asyncio.create_task(asyncio.wait_for(operation, 0.01))
            await asyncio.sleep(0.05)
        else:
            for _ in range(2):
                operation.cancel()
                await asyncio.sleep(0)
        assert not operation.done() and not waiter.done() and not finished.is_set()
        release.set()
        error = {'cancel': asyncio.CancelledError, 'timeout': TimeoutError, 'worker_failure': OSError}[interruption]
        with pytest.raises(error):
            await asyncio.wait_for(waiter, 5)
        assert finished.is_set() and all(handle.closed for handle in handles)
        assert len(clients) == 1 and clients[0].http._client.is_closed
        if stage == 'summary' and interruption != 'worker_failure':
            payload = json.loads(await files.read_file('summary.json'))
            assert payload['iterations'] == 1 and payload['stop_reason'] == 'max_idle_streak'
        else:
            assert not await asyncio.to_thread((tmp_path / 'summary.json').exists)
    finally:
        release.set()
        await asyncio.gather(operation, waiter, return_exceptions=True)
        for client in clients:
            await client.close()


@pytest.mark.parametrize('body_failure,cleanup_failure', [(False, False), (True, False), (False, True), (True, True)])
async def test_repeated_interruption_preserves_cleanup_and_original_failure(tmp_path, monkeypatch, body_failure, cleanup_failure):
    runner, clients, adapter_type = local_runner(tmp_path, monkeypatch, fetch_failure=body_failure)
    entered, release = asyncio.Event(), asyncio.Event()
    original_close = adapter_type.close

    async def held_close(adapter):
        entered.set()
        await release.wait()
        await original_close(adapter)
        if cleanup_failure:
            raise OSError('controlled-cleanup-failure')

    monkeypatch.setattr(adapter_type, 'close', held_close)
    operation = asyncio.create_task(runner.run(worker_id='cleanup-worker', max_idle_streak=1))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        for _ in range(2):
            operation.cancel()
            await asyncio.sleep(0)
        assert not operation.done() and len(clients) == 1 and not clients[0].http._client.is_closed
        release.set()
        expected = BaseExceptionGroup if body_failure and cleanup_failure else (
            OSError if cleanup_failure else RuntimeError if body_failure else asyncio.CancelledError)
        with pytest.raises(expected) as raised:
            await asyncio.wait_for(operation, 5)
        if body_failure and cleanup_failure:
            assert [str(error) for error in raised.value.exceptions] == ['controlled-fetch-failure', 'controlled-cleanup-failure']
        elif body_failure or cleanup_failure:
            assert str(raised.value) == ('controlled-cleanup-failure' if cleanup_failure else 'controlled-fetch-failure')
        assert clients[0].http._client.is_closed
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        for client in clients:
            await original_close(client)
