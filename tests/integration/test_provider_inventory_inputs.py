"""Layer: integration. Real HTTP/file inventory with controlled admission and interruption."""
import asyncio
import json
import threading
from contextlib import asynccontextmanager

import pytest

from orket.adapters.llm.local_model_provider_runtime_target import ensure_provider_runtime_target
from orket.application.services.local_model_factory import create_local_model_provider
from orket.runtime.config import provider_runtime_target as targeting

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def _inventory_server():
    arrived, release = asyncio.Event(), asyncio.Event()
    owners, failures = set(), []

    async def respond(reader, writer):
        task = asyncio.current_task()
        owners.add(task)
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            assert request.startswith(b"GET /v1/models ")
            arrived.set()
            await release.wait()
            body = json.dumps({"data": [{"id": "fixture"}]}).encode()
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode() + body)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            failures.append(type(exc).__name__)
        finally:
            writer.close()
            await writer.wait_closed()
            owners.remove(task)

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    try:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1", arrived, release
    finally:
        release.set()
        server.close()
        await server.wait_closed()
        if owners:
            await asyncio.wait_for(asyncio.gather(*owners), timeout=5)
        assert not owners and not failures


def _options(url):
    return dict(provider="llama_cpp", requested_model="fixture", base_url=url,
                timeout_s=5, auto_select_model=False, auto_load_local_model=False,
                model_load_timeout_s=5, model_ttl_sec=0)


def _files(tmp_path):
    first, second = tmp_path/"first", tmp_path/"second"
    first.mkdir()
    second.mkdir()
    (first/"fixture.gguf").write_bytes(b"inventory fixture; no model inference")
    (second/"unrelated.gguf").write_bytes(b"other inventory fixture")
    return first, second


async def test_provider_preparation_captures_environment_before_http_discovery(tmp_path, monkeypatch):
    first, second = await asyncio.to_thread(_files, tmp_path)
    monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(first))
    monkeypatch.setenv("ORKET_PROVIDER_QUARANTINE", "")
    monkeypatch.setenv("ORKET_PROVIDER_MODEL_QUARANTINE", "")
    async with _inventory_server() as (url, arrived, release):
        operation = asyncio.create_task(targeting.resolve_provider_runtime_target(**_options(url)))
        try:
            await asyncio.wait_for(arrived.wait(), timeout=5)
            monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(second))
            release.set()
            result = await operation
            assert result.status == "OK"
            assert result.gguf_model_root == str(first.resolve())
            assert result.model_id == "fixture"
        finally:
            release.set()
            await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.parametrize("worker_failure", [False, True], ids=["success", "worker-failure"])
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
async def test_provider_inventory_retains_worker_through_repeated_cancellation(
    tmp_path, monkeypatch, worker_failure, interrupt,
):
    first, _ = await asyncio.to_thread(_files, tmp_path)
    monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(first))
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = targeting._inventory_gguf_models_sync

    def held(**kwargs):
        entered.set()
        assert release.wait(5), "test worker release was not delivered"
        try:
            result = original(**kwargs)
            if worker_failure:
                raise OSError("observed inventory worker failure")
            return result
        finally:
            finished.set()

    monkeypatch.setattr(targeting, "_inventory_gguf_models_sync", held)
    async with _inventory_server() as (url, _, http_release):
        http_release.set()
        operation = asyncio.create_task(targeting.resolve_provider_runtime_target(**_options(url)))
        waiter = operation
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            if interrupt == "timeout":
                waiter = asyncio.create_task(asyncio.wait_for(operation, timeout=0.01))
                await _responsive_tick(0.03)
            else:
                for _ in range(2):
                    operation.cancel()
                    await _responsive_tick(0.01)
            assert not operation.done(), "provider preparation detached its admitted worker"
            assert not waiter.done()
            assert not finished.is_set()
            release.set()
            expected = OSError if worker_failure else (TimeoutError if interrupt == "timeout" else asyncio.CancelledError)
            with pytest.raises(expected):
                await waiter
            assert finished.is_set()
        finally:
            release.set()
            await asyncio.gather(waiter, operation, return_exceptions=True)
            assert await asyncio.to_thread(finished.wait, 5)


async def _responsive_tick(seconds):
    # Predeclared bound, measured independently of callback ordering in wait_for.
    loop = asyncio.get_running_loop()
    started = loop.time()
    await asyncio.wait_for(asyncio.sleep(seconds), timeout=0.5)
    assert loop.time() - started < 0.5


async def test_explicit_provider_environment_is_captured_and_overrides_process_inputs(tmp_path, monkeypatch):
    first, second = await asyncio.to_thread(_files, tmp_path)
    monkeypatch.setenv("ORKET_PROVIDER_QUARANTINE", "llama_cpp")
    monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(second))
    supplied = {"ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": str(first)}
    async with _inventory_server() as (url, arrived, release):
        operation = asyncio.create_task(targeting.resolve_provider_runtime_target(**_options(url), environment=supplied))
        try:
            await asyncio.wait_for(arrived.wait(), timeout=5)
            supplied["ORKET_LLAMA_CPP_GGUF_MODEL_ROOT"] = str(second)
            supplied["ORKET_PROVIDER_QUARANTINE"] = "llama_cpp"
            release.set()
            result = await operation
            assert result.status == "OK"
            assert result.gguf_model_root == str(first.resolve())
        finally:
            release.set()
            await asyncio.gather(operation, return_exceptions=True)


async def test_inference_client_retains_supplied_preparation_settings(tmp_path, monkeypatch):
    first, second = await asyncio.to_thread(_files, tmp_path)
    supplied = {"ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": str(first), "ORKET_LLM_PROVIDER": "llama_cpp"}
    async with _inventory_server() as (url, _, release):
        release.set()
        provider = create_local_model_provider(model="fixture", base_url=url, environment=supplied)
        try:
            supplied["ORKET_LLAMA_CPP_GGUF_MODEL_ROOT"] = str(second)
            monkeypatch.setenv("ORKET_PROVIDER_QUARANTINE", "llama_cpp")
            monkeypatch.setenv("ORKET_LLAMA_CPP_GGUF_MODEL_ROOT", str(second))
            assert await ensure_provider_runtime_target(provider) == "fixture"
            assert provider._runtime_target.to_payload()["gguf_model_root"] == str(first.resolve())
        finally:
            await provider.close()
        assert provider.client.is_closed


async def test_concurrent_provider_inventories_keep_separate_settings(tmp_path):
    first, second = await asyncio.to_thread(_files, tmp_path)
    async with _inventory_server() as a, _inventory_server() as b:
        operations = [asyncio.create_task(targeting.resolve_provider_runtime_target(
            **_options(server[0]), environment={"ORKET_LLAMA_CPP_GGUF_MODEL_ROOT": str(root)},
        )) for server, root in ((a, first), (b, second))]
        try:
            await asyncio.wait_for(asyncio.gather(a[1].wait(), b[1].wait()), timeout=5)
            a[2].set()
            b[2].set()
            results = await asyncio.gather(*operations)
            assert [r.status for r in results] == ["OK", "BLOCKED"]
            assert [r.gguf_model_root for r in results] == [str(first.resolve()), str(second.resolve())]
        finally:
            a[2].set()
            b[2].set()
            await asyncio.gather(*operations, return_exceptions=True)
