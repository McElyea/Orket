"""Layer: integration. Actual Gitea clients stay owned through native work and cleanup."""
import asyncio
import ssl
import threading

import httpx
import pytest

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.captured_http_client_service import CapturedHttpClientService
from orket.application.services.gitea_state_adapter_factory import create_gitea_state_adapter
from orket.application.services.gitea_webhook_runtime import GiteaWebhookHandler
from tests.helpers.gitea_http_observation import create_gitea_owner, http_client, observe_request, observe_resources
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_gitea_http_input_capture import response_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def interrupt(task, mode, deadline):
    if mode == 'timeout':
        deadline.reschedule(asyncio.get_running_loop().time() + .01)
    else:
        task.cancel()
    await asyncio.sleep(.03)
    if mode == 'repeated':
        task.cancel()
        await asyncio.sleep(.01)
    assert not task.done()


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
@pytest.mark.parametrize('fail', [False, True], ids=['constructed', 'trust-failure'])
async def test_gitea_retains_native_trust_load(tmp_path, monkeypatch, record_property, kind, mode, fail):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    worker = []
    original = ssl.SSLContext.load_verify_locations
    resources, closed = observe_resources(monkeypatch)

    def held(context, *args, **options):
        worker.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(5), 'Gitea trust loading escaped its native owner'
            if fail:
                options['cafile'] = str(tmp_path / 'missing.pem')
            return original(context, *args, **options)
        finally:
            finished.set()

    monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', held)
    timeout = asyncio.timeout(None)
    async with observed_http_server(response_for(kind, 'unused')) as server:
        async def invoke():
            async with timeout:
                return await create_gitea_owner(kind, tmp_path, server[0], environment={}, cwd=tmp_path)

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert len(worker) == 1 and worker[0] != threading.get_ident()
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            await interrupt(task, mode, timeout)
            assert not finished.is_set() and not server[1]
            release.set()
            expected = FileNotFoundError if fail else (TimeoutError if mode == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set() and not server[1]
        assert resources == [] if fail else len(resources) == 2
        assert all(resource in closed for resource in resources)
        assert all(resource.is_closed for resource in resources if isinstance(resource, httpx.AsyncClient))


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('fail_after', [1, 2])
async def test_gitea_partial_construction_drains_acquired_resources(tmp_path, monkeypatch, kind, fail_after):
    resources, closed = observe_resources(monkeypatch, fail_after=fail_after)
    async with observed_http_server(response_for(kind, 'unused')) as server:
        with pytest.raises(OSError, match='after actual HTTP resource acquisition'):
            await create_gitea_owner(kind, tmp_path, server[0], environment={}, cwd=tmp_path)
        assert len(resources) == fail_after and all(resource in closed for resource in resources)
        assert all(resource.is_closed for resource in resources if isinstance(resource, httpx.AsyncClient))
        assert not server[1]


@pytest.mark.parametrize('kind', ['state', 'webhook'])
async def test_gitea_failed_construction_preserves_cleanup_failure(tmp_path, monkeypatch, kind):
    resources, _closed = observe_resources(monkeypatch, fail_after=2)
    original = httpx.AsyncClient.aclose
    errors = []

    async def failed_close(client):
        await original(client)
        error = OSError('controlled failure after physical HTTP close')
        errors.append(error)
        raise error

    monkeypatch.setattr(httpx.AsyncClient, 'aclose', failed_close)
    with pytest.raises(BaseExceptionGroup) as outcome:
        await create_gitea_owner(kind, tmp_path, 'http://127.0.0.1:1', environment={}, cwd=tmp_path)
    assert len(resources) == 2 and resources[-1].is_closed
    assert isinstance(outcome.value.exceptions[0], OSError)
    assert 'after actual HTTP resource acquisition' in str(outcome.value.exceptions[0])
    assert outcome.value.exceptions[1].exceptions == tuple(errors) and len(errors) == 1


@pytest.mark.parametrize('kind', ['state', 'webhook'])
@pytest.mark.parametrize('mode', ['cancel', 'repeated', 'timeout'])
@pytest.mark.parametrize('failure', [False, True], ids=['clean-close', 'close-failure'])
async def test_gitea_close_retains_actual_transport_and_failure(tmp_path, monkeypatch, kind, mode, failure):
    entered, release = asyncio.Event(), asyncio.Event()
    original = httpx.AsyncClient.aclose
    errors = []

    async def held(client):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        await original(client)
        if failure:
            error = OSError('controlled failure after physical Gitea close')
            errors.append(error)
            raise error

    monkeypatch.setattr(httpx.AsyncClient, 'aclose', held)
    resources, closed = observe_resources(monkeypatch)
    timeout = asyncio.timeout(None)
    async with observed_http_server(response_for(kind, 'observed')) as server:
        owner = await create_gitea_owner(kind, tmp_path, server[0], environment={}, cwd=tmp_path)
        assert await observe_request(owner) == ([] if kind == 'state' else {'version': 'observed'})

        async def invoke():
            async with timeout:
                await owner.close()

        task = asyncio.create_task(invoke())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            await interrupt(task, mode, timeout)
            assert not http_client(owner).is_closed
            release.set()
            expected = (RuntimeError if kind == 'webhook' else BaseExceptionGroup) if failure else (
                TimeoutError if mode == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected) as outcome:
                await asyncio.wait_for(asyncio.shield(task), 5)
            if failure:
                cause = outcome.value.__cause__ if kind == 'webhook' else outcome.value
                assert isinstance(cause, BaseExceptionGroup) and cause.exceptions == tuple(errors)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert http_client(owner).is_closed and len(server[1]) == 1
        assert len(resources) == 2 and resources[0] in closed
        assert failure or all(resource in closed for resource in resources)


@pytest.mark.parametrize('entry', ['state-factory', 'state-adapter', 'webhook'])
async def test_gitea_native_entry_refuses_before_keylog_and_durable_effects(tmp_path, entry):
    environment = {'SSLKEYLOGFILE': str(tmp_path / 'must-not-exist.log')}
    options = dict(base_url='https://127.0.0.1:1', owner='fixture', repo='fixture', token='public-token')
    with pytest.raises(RuntimeError, match='REQUIRES_ASYNC_OWNER'):
        if entry == 'state-factory':
            create_gitea_state_adapter(environment=environment, cwd=tmp_path, **options)
        elif entry == 'state-adapter':
            GiteaStateAdapter(http_client_owner=CapturedHttpClientService(environment=environment, cwd=tmp_path),
                              issue_body_max_bytes=65000, **options)
        else:
            GiteaWebhookHandler(workspace=tmp_path, environment=environment)
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []


@pytest.mark.parametrize('budget', [float('inf'), float('-inf'), float('nan')])
async def test_gitea_nonfinite_timeout_refuses_before_native_effect(tmp_path, monkeypatch, budget):
    resources, closed = observe_resources(monkeypatch)
    with pytest.raises(ValueError, match='E_HTTP_CLIENT_TIMEOUT_NOT_FINITE'):
        await create_gitea_owner('state', tmp_path, 'http://127.0.0.1:1', cwd=tmp_path,
            environment={'SSLKEYLOGFILE': str(tmp_path / 'must-not-exist.log')}, timeout_seconds=budget)
    assert not resources and not closed and await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
