"""Integration: real HTTP transport ownership; controlled responses are not inference."""
import asyncio
import threading

import httpx
import pytest

from orket.application.services.model_stream_http_service import ModelStreamHttpService
from orket.streaming.model_provider import OllamaModelStreamProvider, OpenAICompatModelStreamProvider
from orket.workloads import model_stream_v1 as workload
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_model_stream_iterator_lifetime import context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observed_clients(monkeypatch, *, closing=None, release=None, failure=None):
    clients, threads = [], []
    for client_type in (httpx.Client, httpx.AsyncClient):
        original = client_type.__init__

        def create(client, *args, _original=original, **options):
            _original(client, *args, **options)
            clients.append(client)
            threads.append(threading.get_ident())

        monkeypatch.setattr(client_type, "__init__", create)
    if closing is not None:
        loop = asyncio.get_running_loop()
        original_close = httpx.AsyncHTTPTransport.aclose
        original_sync_close = httpx.HTTPTransport.close

        async def close(transport):
            closing.set()
            await release.wait()
            await original_close(transport)
            if failure is not None:
                raise failure

        def close_sync(transport):
            loop.call_soon_threadsafe(closing.set)
            asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
            original_sync_close(transport)
            if failure is not None:
                raise failure

        original_exit = httpx.AsyncClient.__aexit__
        original_sync_exit = httpx.Client.__exit__

        async def exit_async(client, *args):
            closing.set()
            await release.wait()
            await original_exit(client, *args)
            if failure is not None:
                raise failure

        def exit_sync(client, *args):
            loop.call_soon_threadsafe(closing.set)
            asyncio.run_coroutine_threadsafe(release.wait(), loop).result(timeout=5)
            original_sync_exit(client, *args)
            if failure is not None:
                raise failure

        monkeypatch.setattr(httpx.AsyncClient, "__aexit__", exit_async)
        monkeypatch.setattr(httpx.Client, "__exit__", exit_sync)
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "aclose", close)
        monkeypatch.setattr(httpx.HTTPTransport, "close", close_sync)
    return clients, threads


def configure(monkeypatch, backend, address):
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false" if backend == "nonstream" else "true")
    provider_class = OllamaModelStreamProvider if backend == "ollama" else OpenAICompatModelStreamProvider
    provider = provider_class(model_id="fixture", base_url=address, timeout_s=2, http_client_owner=ModelStreamHttpService(
        backend="ollama" if backend == "ollama" else "openai_compat", base_url=address, timeout_s=2))

    async def build(**_inputs):
        return provider

    monkeypatch.setattr(workload, "_build_real_provider", build)
    return provider


def responder(backend):
    async def response(request):
        if backend == "ollama":
            assert request[0].startswith("POST /api/chat ")
            return 200, b'{"model":"fixture","message":{"role":"assistant","content":"observed"},"done":true}\n'
        assert request[0].startswith("POST /chat/completions ")
        if request[1]["stream"]:
            return 200, b'data: {"choices":[{"delta":{"content":"observed"}}]}\n\ndata: [DONE]\n\n'
        return 200, {"choices": [{"message": {"content": "observed"}}]}
    return response


async def run(commits):
    async def emit(_kind, _payload):
        return True
    return await workload.run_model_stream_v1(input_config={"prompt": "fixture", "max_tokens": 1},
        turn_params={}, interaction_context=context(emit, commits))


@pytest.mark.parametrize("backend", ["stream", "nonstream", "ollama"])
async def test_transport_constructs_off_loop_and_closes_before_commit(monkeypatch, backend):
    clients, threads = observed_clients(monkeypatch)
    commits = []
    async with observed_http_server(responder(backend), content_type="text/event-stream") as server:
        provider = configure(monkeypatch, backend, server[0])
        try:
            assert await asyncio.wait_for(run(commits), 5) == {"post_finalize_wait_ms": 0}
            assert len(server[1]) == 1 and commits[0].type == "turn_finalize"
            assert clients and all(client.is_closed for client in clients), "client escaped invocation cleanup"
            assert all(thread != threading.get_ident() for thread in threads), "native client constructed on event loop"
            assert not provider._canceled
        finally:
            for client in clients:
                if isinstance(client, httpx.AsyncClient):
                    await client.aclose()
                else:
                    await asyncio.to_thread(client.close)


@pytest.mark.parametrize("backend", ["stream", "nonstream", "ollama"])
@pytest.mark.parametrize("close_failure", [False, True])
async def test_transport_close_is_retained_and_failure_refuses_commit(monkeypatch, backend, close_failure):
    closing, release = asyncio.Event(), asyncio.Event()
    failure = OSError("controlled actual client close failure") if close_failure else None
    clients, _threads = observed_clients(monkeypatch, closing=closing, release=release, failure=failure)
    commits = []
    async with observed_http_server(responder(backend), content_type="text/event-stream") as server:
        configure(monkeypatch, backend, server[0])
        task = asyncio.create_task(run(commits))
        waiter = asyncio.create_task(closing.wait())
        try:
            await asyncio.wait([task, waiter], timeout=3, return_when=asyncio.FIRST_COMPLETED)
            assert closing.is_set() and not task.done(), "workload escaped actual client cleanup"
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
            assert not task.done() and not commits
            release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            if close_failure:
                assert failure in leaves(outcome)
            else:
                assert isinstance(outcome, asyncio.CancelledError)
            assert not commits and clients and all(client.is_closed for client in clients)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
            for client in clients:
                try:
                    if isinstance(client, httpx.AsyncClient):
                        await client.aclose()
                    else:
                        await asyncio.to_thread(client.close)
                except OSError as exc:
                    assert exc is failure


def leaves(outcome):
    if isinstance(outcome, BaseExceptionGroup):
        return [leaf for child in outcome.exceptions for leaf in leaves(child)]
    return [outcome]
