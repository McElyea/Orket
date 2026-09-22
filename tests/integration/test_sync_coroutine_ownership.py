"""Layer: integration. Native owners retain real HTTP and cleanup through interruption."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.execution.sync_coroutine_owner import SyncCoroutineOwner
from orket.exceptions import ModelProviderError
from orket_extension_sdk.llm import GenerateRequest
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_piper_process_lifetime import tree_provider
from tests.integration.test_sync_coroutine_boundaries import model_provider
from tests.integration.test_verification_process_lifetime import assert_stopped, await_tree, stop_observed

pytestmark = pytest.mark.integration


def test_owner_keeps_loop_affinity_across_threads_with_fresh_caller_context():
    context = ContextVar("sync-owner-test-context", default="outside")
    barrier, owner = threading.Barrier(2), SyncCoroutineOwner()

    async def observe():
        value = context.get()
        context.set("task-local-change")
        return value, asyncio.get_running_loop()

    def worker(value):
        context.set(value)
        sentinel = asyncio.new_event_loop()
        asyncio.set_event_loop(sentinel)
        try:
            barrier.wait(10)
            result = owner.run(observe())
            assert context.get() == value and asyncio.get_event_loop() is sentinel
            return result, threading.get_ident()
        finally:
            asyncio.set_event_loop(None)
            sentinel.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = [
                future.result(timeout=10) for future in [workers.submit(worker, value) for value in ("first", "second")]
            ]
    finally:
        owner.close()
    assert [result[0][0] for result in results] == ["first", "second"]
    assert results[0][0][1] is results[1][0][1] and results[0][0][1].is_closed()
    assert results[0][1] != results[1][1] and context.get() == "outside"


def test_finalizer_failure_closes_loop_and_is_retained_without_running_it_again(tmp_path):
    owner, failure, calls = SyncCoroutineOwner(), OSError("fixture finalizer failure"), []

    async def observe():
        return asyncio.get_running_loop(), await asyncio.to_thread(threading.current_thread)

    async def finalizer():
        calls.append("cleanup")
        await asyncio.to_thread((tmp_path / "cleanup").write_bytes, b"cleanup observed")
        raise failure

    loop, worker = owner.run(observe())
    for _ in range(2):
        with pytest.raises(OSError) as caught:
            owner.close(finalizer)
        assert caught.value is failure
    assert calls == ["cleanup"] and (tmp_path / "cleanup").read_bytes() == b"cleanup observed"
    assert loop.is_closed() and not worker.is_alive() and owner.closed and not owner.accepting


def test_operation_and_async_generator_cleanup_failures_are_both_preserved(tmp_path):
    primary, cleanup = OSError("fixture operation failure"), ValueError("fixture generator cleanup failure")
    retained, loops = [], []

    async def resource():
        try:
            yield "resource"
        finally:
            await asyncio.to_thread((tmp_path / "generator-cleanup").write_bytes, b"closed")
            raise cleanup

    async def operation():
        loops.append(asyncio.get_running_loop())
        generator = resource()
        retained.append(generator)
        assert await anext(generator) == "resource"
        raise primary

    with pytest.raises(BaseExceptionGroup) as caught, SyncCoroutineOwner() as owner:
        owner.run(operation())
    assert caught.value.exceptions == (primary, cleanup)
    assert loops[0].is_closed() and (tmp_path / "generator-cleanup").read_bytes() == b"closed"
    assert retained[0].ag_frame is None


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancel", "timeout", "transport-failure"])
async def test_real_sdk_http_generation_and_close_stay_owned(tmp_path, record_property, interruption):
    entered, release = asyncio.Event(), asyncio.Event()

    async def response(request):
        if request[0].startswith("GET"):
            return 200, {"data": [{"id": "odr-fixture-model"}]}
        entered.set()
        await asyncio.wait_for(release.wait(), 10)
        if interruption == "transport-failure":
            return 400, {"error": "fixture transport failure"}
        return 200, {"model": "odr-fixture-model", "choices": [{"message": {"content": "fixture reply"}}]}

    async with observed_http_server(response) as (endpoint, requests):
        provider = await run_owned_thread(partial(model_provider, endpoint + "/v1"), label="fixture-sdk-construction")
        active = asyncio.create_task(
            run_owned_thread(
                partial(provider.generate, GenerateRequest(system_prompt="", user_message="owned fixture")),
                label="SDK native generation",
            )
        )
        closing = waiter = None
        try:
            await asyncio.wait_for(entered.wait(), 10)
            closing = asyncio.create_task(run_owned_thread(provider.close, label="SDK native cleanup"))
            assert await asyncio.wait_for(asyncio.to_thread(provider._coroutines._closing.wait, 10), 10)
            if interruption == "timeout":
                waiter = asyncio.create_task(asyncio.wait_for(active, 0.02))
            else:
                active.cancel()
                await asyncio.sleep(0)
                active.cancel()
            await asyncio.sleep(0.04)
            await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
            assert not active.done() and not closing.done() and not provider.is_available()
            with pytest.raises(RuntimeError, match="E_SDK_MODEL_PROVIDER_CLOSED"):
                await run_owned_thread(
                    partial(provider.generate, GenerateRequest(system_prompt="", user_message="refused")),
                    label="refused SDK generation",
                )
            release.set()
            results = await asyncio.wait_for(
                asyncio.gather(active, closing, *([waiter] if waiter else []), return_exceptions=True), 10
            )
            assert isinstance(
                results[0], ModelProviderError if interruption == "transport-failure" else asyncio.CancelledError
            )
            assert results[1] is None
            if waiter:
                assert isinstance(results[2], TimeoutError)
            assert provider._provider.client.is_closed and provider._coroutines.closed
            assert len([request for request in requests if request[0].startswith("POST")]) == 1
        finally:
            release.set()
            await asyncio.gather(
                active, *([closing] if closing else []), *([waiter] if waiter else []), return_exceptions=True
            )
            await run_owned_thread(provider.close, label="SDK fixture final cleanup")


@pytest.mark.asyncio
async def test_native_piper_call_closes_its_loop_after_real_descendant_cleanup(tmp_path, monkeypatch, record_property):
    provider = await asyncio.to_thread(tree_provider, tmp_path, "leader-exit")
    original, loops = provider.synthesize_async, []

    async def observed(*args):
        loops.append(asyncio.get_running_loop())
        return await original(*args)

    monkeypatch.setattr(provider, "synthesize_async", observed)
    task = asyncio.create_task(
        run_owned_thread(lambda: provider.synthesize("hello", "voice"), label="native Piper coroutine owner")
    )
    processes = []
    try:
        processes = await await_tree(tmp_path)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        await asyncio.to_thread((tmp_path / "release-leader").touch)
        clip = await asyncio.wait_for(task, 10)
        assert clip.samples == b"" and len(loops) == 1 and loops[0].is_closed()
        await assert_stopped(processes, tmp_path)
        assert not await asyncio.to_thread(lambda: list(tmp_path.glob(".orket-piper-*")))
    finally:
        await asyncio.to_thread((tmp_path / "release-leader").touch)
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.to_thread(stop_observed, processes)
