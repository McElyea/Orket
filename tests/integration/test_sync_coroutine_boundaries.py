"""Layer: integration. Native coroutine calls finish their own loop and transport lifetime."""

import asyncio
import inspect
import threading
from functools import partial

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket.application.services.sdk_memory_provider import SQLiteMemoryCapabilityProvider
from orket.capabilities.sync_bridge import run_coro_sync
from orket_extension_sdk.llm import GenerateRequest
from orket_extension_sdk.memory import MemoryQueryRequest, MemoryWriteRequest
from tests.helpers.odr_provider_server import AUDITOR, MODEL, provider_server
from tests.integration.test_piper_process_lifetime import tree_provider

pytestmark = pytest.mark.integration


def model_provider(endpoint):
    return LocalModelCapabilityProvider(
        model=MODEL,
        temperature=0,
        seed=0,
        provider="openai_compat",
        environment={
            "ORKET_LLM_OPENAI_BASE_URL": endpoint,
            "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false",
            "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false",
            "ORKET_DISABLE_SANDBOX": "1",
        },
    )


@pytest.mark.parametrize("resource", ["loop", "executor"])
def test_standalone_call_closes_its_loop_and_executor_after_sqlite(tmp_path, resource):
    async def operation():
        async with aiosqlite.connect(tmp_path / "actual.sqlite3") as connection:
            await connection.execute("CREATE TABLE observations (value INTEGER)")
            await connection.execute("INSERT INTO observations VALUES (42)")
            await connection.commit()
            assert await (await connection.execute("SELECT value FROM observations")).fetchone() == (42,)
        return asyncio.get_running_loop(), await asyncio.to_thread(threading.current_thread)

    loop, executor = run_coro_sync(operation())
    assert (tmp_path / "actual.sqlite3").is_file()
    if resource == "loop":
        assert loop.is_closed()
    else:
        assert not executor.is_alive()


@pytest.mark.asyncio
async def test_direct_bridge_refuses_loop_before_effect_and_closes_unstarted_coroutine(tmp_path):
    path = tmp_path / "forbidden-effect"

    async def operation():
        await asyncio.to_thread(path.write_bytes, b"effect")

    coroutine = operation()
    try:
        with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
            run_coro_sync(coroutine)
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED
        assert not await asyncio.to_thread(path.exists)
    finally:
        coroutine.close()


def test_sdk_model_preserves_http_loop_affinity_and_closes_the_loop(monkeypatch):
    with provider_server() as (endpoint, calls):
        provider = model_provider(endpoint)
        complete, close, loops = provider._provider.complete, provider._provider.close, []

        async def observed_complete(**kwargs):
            loops.append(asyncio.get_running_loop())
            return await complete(**kwargs)

        async def observed_close():
            loops.append(asyncio.get_running_loop())
            await close()

        monkeypatch.setattr(provider._provider, "complete", observed_complete)
        monkeypatch.setattr(provider._provider, "close", observed_close)
        try:
            for _ in range(2):
                response = provider.generate(GenerateRequest(system_prompt="", user_message="protocol fixture"))
                assert response.text == AUDITOR and response.model == MODEL
        finally:
            provider.close()
        assert len(loops) == 3 and all(loop is loops[0] for loop in loops)
        assert provider._provider.client.is_closed and not provider.is_available()
        assert len([call for call in calls if call[0] == "POST"]) == 2
        assert loops[0].is_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["generate", "close"])
async def test_sdk_model_refuses_direct_event_loop_calls_before_transport(boundary):
    with provider_server() as (endpoint, calls):
        provider = await run_owned_thread(partial(model_provider, endpoint), label="fixture-sdk-construction")
        try:
            with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
                if boundary == "generate":
                    provider.generate(GenerateRequest(system_prompt="", user_message="protocol fixture"))
                else:
                    provider.close()
            assert calls == [] and not provider._provider.client.is_closed
        finally:
            await asyncio.to_thread(provider.close)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["write", "query", "clear_session"])
async def test_sdk_memory_refuses_event_loop_before_database_creation(tmp_path, boundary):
    database = tmp_path / "memory.sqlite3"
    provider = SQLiteMemoryCapabilityProvider(database)
    request = {
        "write": MemoryWriteRequest(scope="session_memory", session_id="fixture", key="topic", value="value"),
        "query": MemoryQueryRequest(scope="session_memory", session_id="fixture", query="", limit=10),
        "clear_session": "fixture",
    }[boundary]
    with pytest.raises(RuntimeError, match="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"):
        getattr(provider, boundary)(request)
    assert not await asyncio.to_thread(database.exists)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["discovery", "synthesis"])
async def test_piper_native_entrypoints_refuse_event_loop(tmp_path, boundary):
    provider = await asyncio.to_thread(tree_provider, tmp_path, "leader-exit")
    code = (
        "E_PIPER_DISCOVERY_REQUIRES_ASYNC_OWNER" if boundary == "discovery" else "E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER"
    )
    with pytest.raises(RuntimeError, match=code):
        if boundary == "discovery":
            provider.list_voices()
        else:
            provider.synthesize("", "voice")
