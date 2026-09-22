"""Layer: integration. Actual loopback HTTP transport close cannot escape its audit."""

import asyncio

import pytest

from scripts.audit import replay_turn
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancel", "timeout", "close-failure"])
async def test_audit_retains_actual_provider_close(tmp_path, monkeypatch, record_property, interruption):
    entered, release, created = asyncio.Event(), asyncio.Event(), []
    original_factory = replay_turn.create_local_model_provider

    async def response(request):
        if request[0].startswith("GET"):
            return 200, {"data": [{"id": "fixture-model"}]}
        return 200, {"model": "fixture-model", "choices": [{"message": {"content": "fixture response"}}]}

    async with observed_http_server(response) as (endpoint, requests):

        def construct(**kwargs):
            provider = original_factory(
                **kwargs,
                provider="openai_compat",
                environment={
                    "ORKET_LLM_OPENAI_BASE_URL": endpoint + "/v1",
                    "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false",
                    "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false",
                },
            )
            original_close = provider.close

            async def close():
                entered.set()
                await asyncio.wait_for(release.wait(), 10)
                await original_close()
                if interruption == "close-failure":
                    await asyncio.to_thread((tmp_path / "missing-close-input").read_bytes)

            monkeypatch.setattr(provider, "close", close)
            created.append((provider, original_close))
            return provider

        monkeypatch.setattr(replay_turn, "create_local_model_provider", construct)
        task = asyncio.create_task(
            replay_turn._default_replay_call(
                messages=[{"role": "user", "content": "fixture"}], model="fixture-model", runtime_context={}
            )
        )
        waiter = None
        try:
            await asyncio.wait_for(entered.wait(), 10)
            if interruption == "timeout":
                waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
            else:
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(0.04)
            await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
            assert not task.done() and not created[0][0].client.is_closed
            release.set()
            results = await asyncio.wait_for(
                asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True), 10
            )
            assert isinstance(results[0], OSError if interruption == "close-failure" else asyncio.CancelledError)
            if waiter:
                assert isinstance(results[1], TimeoutError)
            assert len(created) == 1 and created[0][0].client.is_closed
            assert len([request for request in requests if request[0].startswith("POST")]) == 1
        finally:
            release.set()
            await asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True)
            for _, close in created:
                await close()
