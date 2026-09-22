"""Exercise actual executor/bridge workers and client cleanup with controlled inference."""
from __future__ import annotations

import asyncio
import os
import threading
from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.application.services.extension_runtime_support import generate_response
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse

REQUEST = GenerateRequest(system_prompt="", user_message="hello")


class BlockingProvider:
    def __init__(self, marker, *, fail=False):
        self.marker = marker
        self.fail = fail
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def generate(self, request):
        self.entered.set()
        try:
            if not self.release.wait(5):
                raise TimeoutError("Test did not release the worker")
            self.marker.write_text(request.user_message, encoding="utf-8")
            if self.fail:
                raise OSError("worker failed after its effect")
            return GenerateResponse(text="ready", model="controlled", latency_ms=None)
        finally:
            self.finished.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
# Layer: integration
async def test_generation_cancellation_drains_worker_and_preserves_failure(tmp_path, fail):
    provider = BlockingProvider(tmp_path / "effect.txt", fail=fail)
    task = asyncio.create_task(generate_response(request=REQUEST, model_provider=provider,
                                               provider_override="", model_override=""))
    try:
        assert await asyncio.to_thread(provider.entered.wait, 5)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        await asyncio.sleep(0.03)
        assert not task.done(), "Request settled while its worker could still write"
        assert not provider.finished.is_set() and not await asyncio.to_thread(provider.marker.exists)
        provider.release.set()
        with pytest.raises(OSError if fail else asyncio.CancelledError):
            await task
        assert provider.finished.is_set() and await asyncio.to_thread(provider.marker.read_text, encoding="utf-8") == "hello"
    finally:
        provider.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(provider.finished.wait, 5)


@pytest.mark.asyncio
# Layer: integration
async def test_concurrent_overrides_preserve_environment_and_close_clients(monkeypatch):
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "llama_cpp")
    monkeypatch.setenv("ORKET_MODEL_PROVIDER", "llama_cpp")
    entered = {name: threading.Event() for name in ("first", "second")}
    release = {name: threading.Event() for name in entered}
    observed = {}

    async def complete(client, *, messages, runtime_context):
        observed[client.requested_model] = client
        entered[client.requested_model].set()
        assert await asyncio.to_thread(release[client.requested_model].wait, 5)
        return ModelResponse(content="ready", raw={"model": client.requested_model})

    monkeypatch.setattr(LocalModelProvider, "complete", complete)
    default = await run_owned_thread(partial(LocalModelCapabilityProvider, model="default", temperature=0.2, seed=None), label="fixture-sdk-construction")
    tasks = []
    try:
        for name, provider in (("first", "lmstudio"), ("second", "llama_cpp")):
            tasks.append(asyncio.create_task(generate_response(request=REQUEST, model_provider=default,
                                                             provider_override=provider, model_override=name)))
            assert await asyncio.to_thread(entered[name].wait, 5)
            assert os.environ["ORKET_LLM_PROVIDER"] == os.environ["ORKET_MODEL_PROVIDER"] == "llama_cpp"
        release["first"].set()
        await tasks[0]
        assert observed["first"].client.is_closed
        assert not observed["second"].client.is_closed
        release["second"].set()
        await tasks[1]
        assert observed["second"].client.is_closed
        assert [observed[n].provider_name for n in ("first", "second")] == ["lmstudio", "llama_cpp"]
        assert os.environ["ORKET_LLM_PROVIDER"] == os.environ["ORKET_MODEL_PROVIDER"] == "llama_cpp"
    finally:
        for gate in release.values():
            gate.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        # Controlled complete does not bind these clients to the bridge loop.
        await default._provider.close()
        for client in observed.values():
            await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
# Layer: integration
async def test_override_cleanup_settles_before_repeated_cancellation(monkeypatch, fail):
    close_started, close_release = threading.Event(), threading.Event()
    observed = []
    original_close = LocalModelProvider.close

    async def complete(client, *, messages, runtime_context):
        return ModelResponse(content="ready", raw={"model": "override"})

    async def close(client):
        observed.append(client)
        close_started.set()
        assert await asyncio.to_thread(close_release.wait, 5)
        await original_close(client)
        if fail:
            raise OSError("client cleanup failed")

    monkeypatch.setattr(LocalModelProvider, "complete", complete)
    monkeypatch.setattr(LocalModelProvider, "close", close)
    default = await run_owned_thread(partial(LocalModelCapabilityProvider, model="default", temperature=0.2, seed=None), label="fixture-sdk-construction")
    task = asyncio.create_task(generate_response(request=REQUEST, model_provider=default,
                                               provider_override="llama_cpp", model_override="override"))
    try:
        assert await asyncio.to_thread(close_started.wait, 5), "Override client was never closed"
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done()
        close_release.set()
        with pytest.raises(OSError if fail else asyncio.CancelledError):
            await task
        assert len(observed) == 1 and observed[0].client.is_closed
    finally:
        close_release.set()
        await asyncio.gather(task, return_exceptions=True)
        await original_close(default._provider)
