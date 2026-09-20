"""Layer: integration. HTTP reads own real filesystem workers through interruption."""
import asyncio
import threading
from contextlib import AsyncExitStack, nullcontext
from functools import partial

import pytest

from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.integration.test_api_active_request_ownership import serving_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _hold_observation(context, monkeypatch, kind, entered, release, finished, fail):
    host, queries = context.api_runtime_host, context.system_queries
    original = queries.reader._directory if kind == 'explorer' else host.create_member_metrics_reader()

    def held(path):
        entered.set()
        try:
            assert release.wait(5)
            if fail:
                raise OSError('directory observation failed')
            return original(path)
        finally:
            finished.set()

    if kind == 'explorer':
        monkeypatch.setattr(queries.reader, '_directory', held)
        return partial(queries.explorer, '.', context.api_runtime_node), '/v1/system/explorer'
    monkeypatch.setattr(host, 'create_member_metrics_reader', lambda: held)
    return partial(queries.member_metrics, 'selected', held), '/v1/runs/selected/metrics'


@pytest.mark.parametrize('stop', ['cancel', 'timeout', 'shutdown'])
@pytest.mark.parametrize('fail', [False, True])
@pytest.mark.parametrize('kind', ['explorer', 'metrics'])
async def test_api_workspace_retains_worker_and_failure(tmp_path, monkeypatch, stop, fail, kind):
    monkeypatch.setenv('ORKET_API_KEY', 'bt0-local-test-key')
    monkeypatch.setenv('ORKET_DISABLE_SANDBOX', '1')
    monkeypatch.setenv('ORKET_DURABLE_ROOT', str(tmp_path/'.orket/durable'))
    monkeypatch.setenv('ORKET_OUTWARD_PIPELINE_DB_PATH', str(tmp_path/'outward.db'))
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with AsyncExitStack() as lifetime:
        expected_exit = pytest.raises(RuntimeError, match="teardown failed") if fail and stop == "shutdown" else nullcontext()
        lifetime.enter_context(expected_exit)
        client = await lifetime.enter_async_context(
            serving_api(app) if stop == "shutdown" else app.router.lifespan_context(app))
        context = app.state.api_runtime_context
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        invoke, route = _hold_observation(context, monkeypatch, kind, entered, release, finished, fail)
        if stop != 'shutdown':
            # Direct application invocation proves caller cancellation/deadline semantics;
            # the shutdown case below traverses the actual TCP route and ASGI owner.
            request = asyncio.create_task(invoke())
            try:
                assert await asyncio.to_thread(entered.wait, 5)
                waiter = asyncio.create_task(asyncio.wait_for(request, 0.01)) if stop == 'timeout' else request
                if stop == 'cancel':
                    request.cancel()
                    await asyncio.sleep(0)
                    request.cancel()
                await asyncio.sleep(0.03)
                assert not waiter.done() and not finished.is_set()
                release.set()
                expected = OSError if fail else (TimeoutError if stop == 'timeout' else asyncio.CancelledError)
                with pytest.raises(expected):
                    await waiter
            finally:
                release.set()
                await asyncio.gather(request, return_exceptions=True)
                await context.close()
            assert finished.is_set() and context.closed
            return
        await _tcp_shutdown(context, client, entered, release, finished, fail, route)


async def _tcp_shutdown(context, client, entered, release, finished, fail, route):
    request, closing = None, None
    try:
        request = asyncio.create_task(client.get(route))
        assert await asyncio.to_thread(entered.wait, 5)
        started = asyncio.get_running_loop().time()
        heartbeat = await asyncio.wait_for(client.get('/v1/system/heartbeat'), 0.5)
        assert heartbeat.status_code == 200
        assert asyncio.get_running_loop().time() - started <= 0.5
        closing = asyncio.create_task(context.close())
        await asyncio.sleep(0.03)
        assert not closing.done() and not context.closed and not finished.is_set()
        assert context.active_request_count == 1
        release.set()
        if fail:
            with pytest.raises(RuntimeError, match='teardown failed') as observed:
                await closing
            assert isinstance(observed.value.__cause__, OSError)
        else:
            await closing
        assert (await request).status_code == (500 if fail else 503)
        assert finished.is_set() and context.closed is (not fail)
        assert context.active_request_count == 0
    finally:
        release.set()
        await asyncio.gather(*(t for t in (request, closing) if t is not None), return_exceptions=True)
