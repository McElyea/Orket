"""Layer: integration. Retained native inference clients and actual teardown under interruption."""
import asyncio
import ssl
import threading

import httpx
import pytest

from orket.application.services import provider_inference_http_service as service
from orket.application.services.local_model_factory import (
    create_local_model_provider,
    create_local_model_provider_async,
)
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.provider_inference_observation import create_observed_provider, http_transport, observe_completion
from tests.integration.test_provider_inference_http_inputs import response_for

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_resources(monkeypatch, *, fail_after=None):
    resources, closed = [], []
    original = service.build_provider_inference_client

    def build(**options):
        retain = options.pop('own_resource')

        def own(resource):
            retain(resource)
            resources.append(resource)
            name = 'aclose' if callable(getattr(resource, 'aclose', None)) else 'close'
            close = getattr(resource, name)

            async def observed_close():
                await close()
                closed.append(resource)

            monkeypatch.setattr(resource, name, observed_close)
            if fail_after == len(resources):
                raise OSError('controlled acquisition failure after actual resource registration')

        return original(**options, own_resource=own)

    monkeypatch.setattr(service, 'build_provider_inference_client', build)
    return resources, closed


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('interrupt', ['cancel', 'repeated', 'timeout'])
@pytest.mark.parametrize('fail', [False, True], ids=['constructed', 'native-failure'])
async def test_inference_retains_native_construction_and_outcome(tmp_path, monkeypatch, record_property,
                                                               provider, interrupt, fail):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    worker = []
    original = ssl.SSLContext.load_verify_locations
    resources, closed = observe_resources(monkeypatch)

    def held(context, *args, **options):
        worker.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(5), 'native trust read escaped its owner'
            if fail:
                options['cafile'] = str(tmp_path / 'missing-trust.pem')
            return original(context, *args, **options)
        finally:
            finished.set()

    monkeypatch.setattr(ssl.SSLContext, 'load_verify_locations', held)
    timeout = asyncio.timeout(None)
    async with observed_http_server(response_for(provider, 'unused')) as server:
        async def invoke():
            async with timeout:
                return await create_observed_provider(provider, server[0], environment={})

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert len(worker) == 1 and worker[0] != threading.get_ident()
            await responsive_sqlite(tmp_path / 'responsive.sqlite3', record_property)
            if interrupt == 'timeout':
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
            await asyncio.sleep(.03)
            if interrupt == 'repeated':
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done() and not finished.is_set() and not server[1]
            release.set()
            expected = FileNotFoundError if fail else (TimeoutError if interrupt == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set() and not server[1]
        assert resources == [] if fail else len(resources) == 2
        assert all(resource in closed for resource in resources)
        assert all(resource.is_closed for resource in resources if isinstance(resource, httpx.AsyncClient))


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('interrupt', ['cancel', 'repeated', 'timeout'])
@pytest.mark.parametrize('failure', [False, True], ids=['clean-close', 'close-failure'])
async def test_inference_close_is_retained_and_preserves_failure(monkeypatch, provider, interrupt, failure):
    arrived, release = asyncio.Event(), asyncio.Event()
    resources, closed = observe_resources(monkeypatch)
    original = httpx.AsyncClient.aclose
    errors = []

    async def held(client):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        await original(client)
        if failure:
            error = OSError('controlled close failure after actual close')
            errors.append(error)
            raise error

    monkeypatch.setattr(httpx.AsyncClient, 'aclose', held)
    timeout = asyncio.timeout(None)
    async with observed_http_server(response_for(provider, 'observed')) as server:
        client = await create_observed_provider(provider, server[0], environment={})
        transport = http_transport(client)
        assert (await observe_completion(client)).content == 'observed'

        async def invoke():
            async with timeout:
                await client.close()

        task = asyncio.create_task(invoke())
        try:
            await asyncio.wait_for(arrived.wait(), 5)
            if interrupt == 'timeout':
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
            await asyncio.sleep(.03)
            if interrupt == 'repeated':
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done() and not transport.is_closed
            release.set()
            expected = BaseExceptionGroup if failure else (TimeoutError if interrupt == 'timeout' else asyncio.CancelledError)
            with pytest.raises(expected) as outcome:
                await asyncio.wait_for(asyncio.shield(task), 5)
            if failure:
                assert outcome.value.exceptions == tuple(errors)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert transport.is_closed and len(server[1]) == 1 and not client._closed
        assert len(resources) == 2 and resources[0] in closed
        assert failure or all(resource in closed for resource in resources)


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('fail_after', [1, 2])
async def test_failed_native_provider_closes_partial_acquisition(monkeypatch, provider, fail_after):
    resources, closed = observe_resources(monkeypatch, fail_after=fail_after)
    async with observed_http_server(response_for(provider, 'unused')) as server:
        with pytest.raises(OSError, match='controlled acquisition failure'):
            await create_observed_provider(provider, server[0], environment={})
        assert len(resources) == fail_after and not server[1]
        assert all(resource in closed for resource in resources)


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('budget', [float('inf'), float('-inf'), float('nan')])
@pytest.mark.parametrize('field', ['timeout', 'connect_timeout_seconds'])
async def test_nonfinite_inference_budget_refuses_before_acquisition(monkeypatch, provider, budget, field):
    resources, closed = observe_resources(monkeypatch)
    async with observed_http_server(response_for(provider, 'unused')) as server:
        with pytest.raises(ValueError, match='E_PROVIDER_TIMEOUT_NOT_FINITE'):
            await create_local_model_provider_async('fixture', provider=provider, base_url=server[0],
                                                    environment={}, **{field: budget})
        assert not resources and not closed and not server[1]


async def test_native_provider_factory_refuses_loop_before_keylog_creation(tmp_path):
    keylog = tmp_path / 'must-not-exist.log'
    with pytest.raises(RuntimeError, match='E_PROVIDER_FACTORY_REQUIRES_ASYNC_OWNER'):
        create_local_model_provider('fixture', environment={'SSLKEYLOGFILE': str(keylog)})
    assert not await asyncio.to_thread(keylog.exists)


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
async def test_replaced_public_client_does_not_abandon_original_transport(provider):
    async with observed_http_server(response_for(provider, 'observed')) as server:
        client = await create_observed_provider(provider, server[0], environment={})
        original = http_transport(client)
        assert (await observe_completion(client)).content == 'observed'
        replacement = await asyncio.to_thread(httpx.AsyncClient, trust_env=False)
        client.client = replacement
        await client.close()
        assert client._closed and original.is_closed and replacement.is_closed


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
@pytest.mark.parametrize('interrupt', ['cancel', 'repeated', 'timeout'])
async def test_inference_request_interruption_closes_actual_client(provider, interrupt):
    arrived, release = asyncio.Event(), asyncio.Event()
    async def response(request):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        return await response_for(provider, 'late-response')(request)

    timeout = asyncio.timeout(None)
    async with observed_http_server(response, allow_disconnect=True) as server:
        client = await create_observed_provider(provider, server[0], environment={})
        transport = http_transport(client)
        async def invoke():
            async with timeout, client:
                return await observe_completion(client)

        task = asyncio.create_task(invoke())
        try:
            await asyncio.wait_for(arrived.wait(), 5)
            if interrupt == 'timeout':
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
                if interrupt == 'repeated':
                    await asyncio.sleep(0)
                    task.cancel()
            with pytest.raises(TimeoutError if interrupt == 'timeout' else asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 5)
            assert transport.is_closed and len(server[1]) == 1
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize('provider', ['openai_compat', 'ollama'])
async def test_failed_construction_and_cleanup_retain_both_failures(monkeypatch, provider):
    resources, closed = observe_resources(monkeypatch, fail_after=2)
    original = httpx.AsyncClient.aclose
    async def close_then_fail(client):
        await original(client)
        raise ValueError('controlled cleanup failure after actual close')

    monkeypatch.setattr(httpx.AsyncClient, 'aclose', close_then_fail)
    async with observed_http_server(response_for(provider, 'unused')) as server:
        with pytest.raises(BaseExceptionGroup) as outcome:
            await create_observed_provider(provider, server[0], environment={})
        failure, cleanup = outcome.value.exceptions
        assert isinstance(failure, OSError) and 'controlled acquisition' in str(failure)
        assert isinstance(cleanup, ExceptionGroup) and len(cleanup.exceptions) == 1
        assert isinstance(cleanup.exceptions[0], ValueError) and 'controlled cleanup' in str(cleanup.exceptions[0])
        assert len(resources) == 2 and resources[0] in closed and not server[1]
