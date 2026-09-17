"""Layer: integration. Real HTTP approval dispatch owns a real native command tree."""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn

from orket.runtime import CompositionConfig, create_api_app
from tests.helpers.outward_authorization import TEST_API_KEY, approve, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def serving_api(app):
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None, lifespan="on"))
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if serving.done():
                    await serving
                    pytest.fail("Server exited before accepting requests")
                await asyncio.sleep(0.01)
        address = server.servers[0].sockets[0].getsockname()
        async with httpx.AsyncClient(base_url=f"http://{address[0]}:{address[1]}", trust_env=False,
                                     headers={"X-API-Key": TEST_API_KEY}, timeout=30) as client:
            yield client
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 10)
        await app.state.api_runtime_context.close()


@pytest.mark.parametrize("stop", ["normal", "repeated-cancel"])
# Layer: integration
async def test_api_close_settles_active_approval_request(tmp_path, boundary, stop):
    _db, _inputs, calls = boundary
    calls[:] = [{"tool": "run_command", "args": {"command": [
        sys.executable, str(WORKER), str(tmp_path), "2", "detached", "ignore-term", "cancel"]}}]
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    context = app.state.api_runtime_context
    processes, request, closing = [], None, None
    async with serving_api(app) as client:
        try:
            proposal = await submit_sequence(client, calls)
            request = asyncio.create_task(approve(client, proposal))
            processes = await await_tree(tmp_path)
            closing = asyncio.create_task(context.close())
            await asyncio.sleep(0)
            if stop == "repeated-cancel":
                for _ in range(3):
                    closing.cancel()
                    await asyncio.sleep(0)
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(closing, 10)
            else:
                await asyncio.wait_for(closing, 10)
            await assert_stopped(processes, tmp_path)
            assert context.closed and not context.accepting_work
            response = await request
            assert response.status_code == 503, response.text
            assert (await client.get("/health")).status_code == 503
            run = await context.outward_run_store.get("bt0-run")
            assert run.status != "completed"
        finally:
            if not processes:
                processes = await asyncio.to_thread(observe_processes, tmp_path)
            await asyncio.to_thread(stop_observed, processes)
            if request is not None:
                await asyncio.gather(request, return_exceptions=True)
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)
