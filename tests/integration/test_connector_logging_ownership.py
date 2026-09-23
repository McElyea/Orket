"""Layer: integration. Actual interrupted HTTP and logging publication ownership."""
import asyncio
import threading
import time
from pathlib import Path

import pytest

import orket.logging as logging_module
from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.domain.records import IssueRecord
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_short_http_ownership import clean_network

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def held_logging(monkeypatch, workspace, boundary):
    entered, release = threading.Event(), threading.Event()
    threads, timers = [], []
    target, method = (Path, 'mkdir') if boundary == 'directory' else (logging_module, '_append_line_sync')
    original = getattr(target, method)

    def held(path, *args, **options):
        expected = workspace if boundary == 'directory' else workspace / 'orket.log'
        if boundary != 'healthy' and path == expected and not entered.is_set():
            threads.append(threading.get_ident())
            entered.set()
            timer = threading.Timer(.75, release.set)
            timers.append(timer)
            timer.start()
            assert release.wait(5), 'Logging fixture release missed'
        return original(path, *args, **options)

    monkeypatch.setattr(target, method, held)
    return entered, release, threads, timers


@pytest.mark.parametrize('boundary', ['healthy', 'directory', 'write'])
async def test_interrupted_connector_owns_native_log(tmp_path, monkeypatch, record_property, boundary):
    clean_network(monkeypatch)
    workspace = tmp_path / 'workspace'
    service = await OutwardConnectorService.for_workspace(workspace, http_allowlist=('127.0.0.1',))
    entered, release, threads, timers = held_logging(monkeypatch, workspace, boundary)
    request_entered, server_release = asyncio.Event(), asyncio.Event()

    async def response(_request):
        request_entered.set()
        await asyncio.wait_for(server_release.wait(), 5)
        return None

    async with observed_http_server(response, allow_disconnect=True) as server:
        task = asyncio.create_task(service.invoke_with_result('http_get', {'url': server[0]}))
        await asyncio.wait_for(request_entered.wait(), 5)
        started = time.perf_counter()
        task.cancel()

        async def sqlite():
            cards = AsyncCardRepository(tmp_path / 'response.sqlite3')
            await cards.save(IssueRecord(id='probe', seat='fixture', summary='Interrupted connector logging'))
            assert (await cards.get_by_id('probe')).id == 'probe'
            return time.perf_counter() - started

        probe = asyncio.create_task(sqlite())
        try:
            if boundary != 'healthy':
                assert await asyncio.to_thread(entered.wait, 5)
                assert threads == [threads[0]] and threads[0] != threading.get_ident()
                assert not task.done() and not release.is_set()
            elapsed = await asyncio.wait_for(probe, 5)
            record_property('responsive_sqlite_seconds', elapsed)
            assert elapsed < .5
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            server_release.set()
            await asyncio.wait_for(asyncio.gather(task, probe, return_exceptions=True), 5)
            for timer in timers:
                await asyncio.to_thread(timer.join, 5)
            await asyncio.wait_for(asyncio.to_thread(logging_module._log_write_queue.join), 5)
        assert len(server[1]) == 1 and await asyncio.to_thread((workspace / 'orket.log').exists)
