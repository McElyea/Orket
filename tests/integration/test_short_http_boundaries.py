"""Layer: integration. Actual short-request resources survive interruption/failure."""
import asyncio
import ssl
import threading

import httpx
import pytest

from orket.application.services.gitea_artifact_exporter_factory import create_gitea_artifact_exporter
from orket.application.services.owned_http_request_service import OwnedHttpRequestService
from tests.helpers.gitea_http_observation import observe_resources
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_gitea_http_ownership import interrupt
from tests.integration.test_short_http_ownership import clean_network, composed_request, response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
async def test_short_http_retains_native_construction(tmp_path, monkeypatch, record_property, kind, mode):
    clean_network(monkeypatch)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = ssl.SSLContext.load_verify_locations
    workers = []
    resources, closed = observe_resources(monkeypatch)

    def held(context, *args, **options):
        workers.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(5), 'Native trust escaped its request owner'
            return original(context, *args, **options)
        finally:
            finished.set()

    deadline = asyncio.timeout(None)
    async with observed_http_server(response) as server, composed_request(kind, tmp_path, server[0]) as invoke:
        monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', held)

        async def operation():
            async with deadline:
                return await invoke()

        task = asyncio.create_task(operation())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert workers == [workers[0]] and workers[0] != threading.get_ident()
            await responsive_sqlite(tmp_path / 'response.sqlite3', record_property)
            await interrupt(task, mode, deadline)
            assert not finished.is_set() and not server[1]
            release.set()
            with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set() and not server[1]
        assert len(resources) == 2 and all(resource in closed for resource in resources)
        assert resources[-1].is_closed


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
@pytest.mark.parametrize('fail_after', [1, 2])
async def test_short_http_partial_construction_closes_acquired_resources(tmp_path, monkeypatch, kind, fail_after):
    clean_network(monkeypatch)
    async with observed_http_server(response) as server, composed_request(kind, tmp_path, server[0]) as invoke:
        resources, closed = observe_resources(monkeypatch, fail_after=fail_after)
        with pytest.raises(OSError, match='after actual HTTP resource acquisition'):
            await asyncio.wait_for(invoke(), 5)
        assert not server[1] and len(resources) == fail_after
        assert all(resource in closed for resource in resources)
        assert all(resource.is_closed for resource in resources if isinstance(resource, httpx.AsyncClient))


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
async def test_short_http_cleanup_failure_cannot_publish_success(tmp_path, monkeypatch, kind):
    clean_network(monkeypatch)
    original = httpx.AsyncClient.aclose
    clients, errors = [], []

    async def failed_close(client):
        await original(client)
        clients.append(client)
        error = OSError('controlled failure after physical short HTTP close')
        errors.append(error)
        raise error

    async with observed_http_server(response) as server, composed_request(kind, tmp_path, server[0]) as invoke:
        monkeypatch.setattr(httpx.AsyncClient, 'aclose', failed_close)
        with pytest.raises(BaseExceptionGroup) as outcome:
            await asyncio.wait_for(invoke(), 5)
        assert outcome.value.exceptions == tuple(errors) and len(errors) == 1
        assert len(clients) == 1 and clients[0].is_closed and len(server[1]) == 1


@pytest.mark.parametrize('kind', ['export', 'get', 'post'])
@pytest.mark.parametrize('mode', ['repeated', 'timeout'])
async def test_short_http_interrupted_request_confirms_peer_teardown(tmp_path, monkeypatch, kind, mode):
    clean_network(monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()

    async def no_response(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return None

    resources, closed = observe_resources(monkeypatch)
    deadline = asyncio.timeout(None)
    async with (observed_http_server(no_response, allow_disconnect=True) as server,
                composed_request(kind, tmp_path, server[0]) as invoke):
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
                task.cancel()
            with pytest.raises(TimeoutError if mode == 'timeout' else asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(server[1]) == 1 and len(resources) == 2
        assert all(resource in closed for resource in resources) and resources[-1].is_closed


@pytest.mark.parametrize('budget', [float('nan'), float('inf'), float('-inf')])
async def test_short_http_nonfinite_budget_refuses_before_native_effects(tmp_path, budget):
    keylog = tmp_path / 'must-not-exist.log'
    requester = OwnedHttpRequestService(environment={'SSLKEYLOGFILE': str(keylog)}, cwd=tmp_path)
    with pytest.raises(ValueError, match='E_HTTP_CLIENT_TIMEOUT_NOT_FINITE'):
        await requester.request('GET', 'http://127.0.0.1:1', timeout_s=budget)
    assert not await asyncio.to_thread(keylog.exists)


async def test_export_factory_refuses_loop_entry_before_filesystem(tmp_path):
    with pytest.raises(RuntimeError, match='E_GITEA_EXPORT_CONSTRUCTION_REQUIRES_ASYNC_OWNER'):
        create_gitea_artifact_exporter(tmp_path, environment={})
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
