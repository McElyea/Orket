"""Real TCP shutdown drains admitted run reads and preserves native failure."""
import asyncio
from contextlib import AsyncExitStack, nullcontext

import pytest

from orket.interfaces.api import create_api_app
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_api_run_observation_ownership import ROUTES, hold_native_read, seed_observations

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", list(ROUTES))
@pytest.mark.parametrize("failure", [False, True])
async def test_api_run_observation_shutdown_waits_for_native_read(tmp_path, monkeypatch, kind, failure):
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "bt0-local-test-key"})
    async with AsyncExitStack() as lifetime:
        lifetime.enter_context(pytest.raises(RuntimeError, match="teardown failed") if failure else nullcontext())
        client = await lifetime.enter_async_context(serving_api(app))
        context = app.state.api_runtime_context
        log, checkpoint = await seed_observations(app, tmp_path)
        state = hold_native_read(monkeypatch, checkpoint if kind == "targeted-replay" else log, failure)
        request, closing = None, None
        try:
            request = asyncio.create_task(client.get(ROUTES[kind]))
            assert await asyncio.to_thread(state.entered.wait, 5)
            assert (await asyncio.wait_for(client.get("/v1/system/heartbeat"), .5)).status_code == 200
            closing = asyncio.create_task(context.close())
            await asyncio.sleep(.08)
            assert not closing.done() and not context.closed and not state.finished.is_set()
            assert context.active_request_count == 1 and not state.files[0].closed
            state.release.set()
            if failure:
                with pytest.raises(RuntimeError, match="teardown failed") as observed:
                    await asyncio.wait_for(closing, 5)
                assert isinstance(observed.value.__cause__, OSError)
            else:
                await asyncio.wait_for(closing, 5)
            assert (await asyncio.wait_for(request, 5)).status_code == (500 if failure else 503)
            assert state.finished.is_set() and all(stream.closed for stream in state.files)
            assert context.active_request_count == 0
            assert context.closed is (not failure)
        finally:
            state.release.set()
            await asyncio.gather(*(task for task in (request, closing) if task is not None), return_exceptions=True)
            assert await asyncio.to_thread(state.finished.wait, 5)
