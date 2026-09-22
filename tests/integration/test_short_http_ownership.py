"""Layer: integration. Real exporter/builtin HTTP, native trust and SQLite lifetimes."""
import asyncio
import ssl
import threading
import time
from contextlib import asynccontextmanager

import httpcore
import httpx
import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.core.domain.outward_authorization import args_hash
from orket.core.domain.records import IssueRecord
from tests.helpers.gitea_loop_inputs import RecordingClock, construction_inputs, gitea_pipeline
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _ambient_proxy

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def response(_request):
    return 200, {'observed': True}


@asynccontextmanager
async def composed_request(kind, root, address, environment=None):
    if kind == 'export':
        selected = {} if environment is None else dict(environment)
        selected.update(GITEA_URL=address, GITEA_ADMIN_USER='fixture-user',
                        GITEA_ADMIN_PASSWORD='public-password', ORKET_DISABLE_SANDBOX='1')
        pipeline = await gitea_pipeline(root, inputs=construction_inputs(root, environment=selected),
                                        clock=RecordingClock())
        try:
            yield lambda: pipeline.artifact_exporter._request('GET', '/fixture')
        finally:
            await pipeline.close()
    else:
        service = await OutwardConnectorService.for_workspace(root, http_allowlist=('127.0.0.1',))
        arguments = {'url': address + '/fixture'}
        if kind == 'post':
            arguments['body'] = {'nested': ['captured']}
        yield lambda: service.invoke_with_result('http_' + kind, arguments)


def assert_success(kind, result):
    if kind == 'export':
        assert result == 200
    else:
        assert result[0]['outcome'] == 'success' and result[1]['ok']
        assert result[1]['status_code'] == 200


def clean_network(monkeypatch):
    _ambient_proxy(monkeypatch, '')
    monkeypatch.setenv('NO_PROXY', '127.0.0.1')
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'SSLKEYLOGFILE'):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize('mode', ['empty', 'proxy', 'bypass', 'ambient-control'])
async def test_pipeline_export_http_uses_captured_network(tmp_path, monkeypatch, mode):
    async with (observed_http_server(response) as origin, observed_http_server(response) as supplied,
                observed_http_server(response) as ambient):
        _ambient_proxy(monkeypatch, ambient[0])
        environment = {}
        if mode in {'proxy', 'bypass', 'ambient-control'}:
            environment = {'HTTP_PROXY': ambient[0] if mode == 'ambient-control' else supplied[0],
                           'NO_PROXY': '127.0.0.1' if mode == 'bypass' else ''}
        async with composed_request('export', tmp_path, origin[0], environment) as invoke:
            assert await asyncio.wait_for(invoke(), 5) == 200
        expected = 'supplied' if mode == 'proxy' else ('ambient' if mode == 'ambient-control' else 'origin')
        assert {name: len(server[1]) for name, server in
                dict(origin=origin, supplied=supplied, ambient=ambient).items()} == {
                    name: int(name == expected) for name in ('origin', 'supplied', 'ambient')}


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
async def test_short_http_native_trust_keeps_sqlite_responsive(tmp_path, monkeypatch, record_property, kind):
    clean_network(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    threads, clients, timers = [], [], []
    original_load, original_client = ssl.SSLContext.load_verify_locations, httpx.AsyncClient.__init__

    def held(context, *args, **options):
        threads.append(threading.get_ident())
        if not entered.is_set():
            entered.set()
            timer = threading.Timer(.75, release.set)
            timers.append(timer)
            timer.start()
        assert release.wait(5), 'Controlled native trust hold did not release'
        return original_load(context, *args, **options)

    def client(instance, *args, **options):
        original_client(instance, *args, **options)
        clients.append(instance)

    async with observed_http_server(response) as server, composed_request(kind, tmp_path, server[0]) as invoke:
        monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', held)
        monkeypatch.setattr(httpx.AsyncClient, '__init__', client)
        started = time.perf_counter()
        operation = asyncio.create_task(invoke())

        async def sqlite():
            cards = AsyncCardRepository(tmp_path / 'responsive.sqlite3')
            await cards.save(IssueRecord(id='probe', seat='fixture', summary='Actual HTTP responsiveness'))
            assert (await cards.get_by_id('probe')).id == 'probe'
            return time.perf_counter() - started

        probe = asyncio.create_task(sqlite())
        try:
            result, elapsed = await asyncio.wait_for(asyncio.gather(operation, probe), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(operation, probe, return_exceptions=True), 5)
            for timer in timers:
                await asyncio.to_thread(timer.join, 5)
        assert_success(kind, result)
        assert len(server[1]) == len(clients) == 1 and clients[0].is_closed
        record_property('independent_sqlite_seconds', elapsed)
        assert elapsed < .5  # Existing D1 bound; controlled native hold is deliberately longer.
        assert entered.is_set() and threads and threading.get_ident() not in threads


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
async def test_short_http_retains_actual_close_through_interruption(tmp_path, monkeypatch, kind, mode):
    clean_network(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    clients, transports, closed = [], [], []
    original, original_client = httpcore.AsyncConnectionPool.aclose, httpx.AsyncClient.__init__

    def client(instance, *args, **options):
        original_client(instance, *args, **options)
        clients.append(instance)

    async def held(transport):
        transports.append(transport)
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        await original(transport)
        closed.append(transport)

    deadline = asyncio.timeout(None)
    async with observed_http_server(response) as server, composed_request(kind, tmp_path, server[0]) as invoke:
        monkeypatch.setattr(httpcore.AsyncConnectionPool, 'aclose', held)
        monkeypatch.setattr(httpx.AsyncClient, '__init__', client)

        async def operation():
            async with deadline:
                return await invoke()

        task = asyncio.create_task(operation())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if mode == 'timeout':
                deadline.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
            await asyncio.sleep(.03)
            if mode == 'repeated':
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done() and not closed
            release.set()
            with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert clients[0].is_closed and len(server[1]) == 1
            assert transports and all(transport in closed for transport in transports)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            # A failing pre-fix control may abandon close; the fixture owns cleanup.
            for transport in transports:
                if transport not in closed:
                    await original(transport)


async def test_builtin_http_event_identity_keeps_the_sent_body(tmp_path, monkeypatch):
    clean_network(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()

    async def held(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return 200, {'observed': True}

    service = await OutwardConnectorService.for_workspace(tmp_path, http_allowlist=('127.0.0.1',))
    async with observed_http_server(held) as server:
        arguments = {'url': server[0], 'body': {'nested': ['sent']}}
        identity = args_hash(arguments)
        task = asyncio.create_task(service.invoke_with_result('http_post', arguments))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            arguments['body']['nested'].append('changed')
            release.set()
            event, result = await asyncio.wait_for(asyncio.shield(task), 5)
            assert result['ok'] and server[1][0][1] == {'nested': ['sent']}
            assert event['args_hash'] == identity
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
