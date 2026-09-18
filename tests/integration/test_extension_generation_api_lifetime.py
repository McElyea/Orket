"""Actual TCP requests retain controlled model workers through application shutdown."""
from __future__ import annotations

import asyncio
import threading

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.integration.test_api_active_request_ownership import serving_api


@pytest.fixture
def generation_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_API_KEY", "bt0-local-test-key")
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "llama_cpp")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / ".orket/durable"))
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(tmp_path / "outward.db"))
    # Public bootstrap constructs the app before the event loop starts.
    return create_api_app(CompositionConfig(project_root=tmp_path))


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [False, True])
# Layer: integration
async def test_tcp_generation_shutdown_waits_for_worker_and_closes_all_clients(generation_app, monkeypatch, tmp_path, override):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    clients = []
    marker = tmp_path / "worker-effect.txt"

    async def complete(client, *, messages, runtime_context):
        clients.append(client)
        entered.set()
        assert await asyncio.to_thread(release.wait, 5)
        await asyncio.to_thread(marker.write_text, "finished", encoding="utf-8")
        finished.set()
        return ModelResponse(content="ready", raw={"model": "controlled"})

    monkeypatch.setattr(LocalModelProvider, "complete", complete)
    context = generation_app.state.api_runtime_context
    default = context.extension_runtime_service._model_provider
    request, closing = None, None
    async with serving_api(generation_app) as client:
        try:
            body = {"user_message": "hello"}
            if override:
                body.update(provider="llama_cpp", model="controlled")
            request = asyncio.create_task(client.post("/v1/extensions/orket.test/runtime/llm/generate", json=body))
            assert await asyncio.to_thread(entered.wait, 5)
            closing = asyncio.create_task(context.close())
            for _ in range(3):
                await asyncio.sleep(0)
                closing.cancel()
            await asyncio.sleep(0.03)
            assert not closing.done() and not context.closed and context.active_request_count == 1
            assert not finished.is_set() and not default._provider.client.is_closed
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await closing
            assert (await request).status_code == 503
            assert context.closed and context.active_request_count == 0
            assert finished.is_set() and await asyncio.to_thread(marker.read_text, encoding="utf-8") == "finished"
            assert default._provider.client.is_closed and all(c.client.is_closed for c in clients)
            assert not default.is_available()
        finally:
            release.set()
            await asyncio.gather(*(t for t in (request, closing) if t is not None), return_exceptions=True)


@pytest.mark.asyncio
# Layer: integration
async def test_tcp_generation_success_closes_default_client_at_lifespan_exit(generation_app, monkeypatch):
    async def complete(client, *, messages, runtime_context):
        return ModelResponse(content="ready", raw={"model": "controlled"})

    monkeypatch.setattr(LocalModelProvider, "complete", complete)
    context = generation_app.state.api_runtime_context
    default = context.extension_runtime_service._model_provider
    async with serving_api(generation_app) as client:
        response = await client.post("/v1/extensions/orket.test/runtime/llm/generate", json={"user_message": "hello"})
        assert response.status_code == 200 and response.json()["text"] == "ready"
        assert not default._provider.client.is_closed
    assert context.closed and default._provider.client.is_closed


@pytest.mark.asyncio
# Layer: contract
async def test_injected_provider_remains_owned_by_embedding(tmp_path):
    class BorrowedProvider:
        def close(self):
            pytest.fail("Embedding-owned provider was closed by the service")

    service = ExtensionRuntimeService(project_root=tmp_path, model_provider=BorrowedProvider())
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_default_client_cleanup_failure_prevents_closed_claim(generation_app, monkeypatch):
    context = generation_app.state.api_runtime_context
    provider = context.extension_runtime_service._model_provider
    original_close = provider.close
    entered, release = threading.Event(), threading.Event()

    def close():
        entered.set()
        assert release.wait(5)
        original_close()
        raise OSError("controlled cleanup failure")

    monkeypatch.setattr(provider, "close", close)
    closing = asyncio.create_task(context.close())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done() and not context.closed
        release.set()
        with pytest.raises(RuntimeError, match="teardown failed") as observed:
            await closing
        assert isinstance(observed.value.__cause__, OSError)
        assert not context.closed and provider._provider.client.is_closed
        with pytest.raises(RuntimeError) as repeated:
            await context.close()
        assert repeated.value is observed.value
    finally:
        release.set()
        await asyncio.gather(closing, return_exceptions=True)
