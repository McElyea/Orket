"""Layer: integration. Observe API teardown through actual listening sockets."""
from __future__ import annotations

import asyncio
import sys

import httpx
import pytest
import uvicorn

from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class HeldListener:
    """Synchronization delays real resource closure; it supplies no fake result."""

    def __init__(self, server):
        self.server = server
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def aclose(self):
        self.entered.set()
        await self.release.wait()
        self.server.close()
        await self.server.wait_closed()


async def listener():
    server = await asyncio.start_server(lambda _reader, writer: writer.close(), "127.0.0.1", 0)
    return HeldListener(server), server.sockets[0].getsockname()


async def accepts_connections(address):
    try:
        # Windows loopback refusal can take longer than one second; timeout is
        # still a probe failure, never evidence that the listener closed.
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(*address), 5)
    except ConnectionRefusedError:
        return False
    writer.close()
    await writer.wait_closed()
    return True


@pytest.mark.parametrize("stop", ["normal", "cancel", "repeated-cancel", "concurrent"])
# Layer: integration
async def test_container_close_waits_for_real_resources_through_cancellation(tmp_path, boundary, stop):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with app.router.lifespan_context(app):
        context = app.state.api_runtime_context
        resource, address = await listener()
        context.register_owned_resource(resource)
        assert await accepts_connections(address)
        first = asyncio.create_task(context.close())
        second = None
        try:
            await asyncio.wait_for(resource.entered.wait(), 5)
            assert not context.closed and not context.accepting_work
            with pytest.raises(RuntimeError, match="closed"):
                context.register_owned_resource(object())
            if stop == "concurrent":
                second = asyncio.create_task(context.close())
                await asyncio.sleep(0)
                assert not second.done(), "A concurrent close returned while the owned socket still accepts connections"
            if stop in {"cancel", "repeated-cancel"}:
                for _ in range(3 if stop == "repeated-cancel" else 1):
                    first.cancel()
                    await asyncio.sleep(0)
            resource.release.set()
            if stop in {"cancel", "repeated-cancel"}:
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(first, 5)
            else:
                await asyncio.wait_for(first, 5)
            if second is not None:
                await asyncio.wait_for(second, 5)
            await context.close()
            assert not await accepts_connections(address), "API close left its actual owned listener open"
            assert context.closed and context.active_background_task_count == 0
        finally:
            resource.release.set()
            await asyncio.gather(first, *([second] if second is not None else []), return_exceptions=True)
            # Counterexample cleanup is explicit and does not count as application proof.
            resource.server.close()
            await resource.server.wait_closed()
            await context.close()
            await context.engine.close()


@pytest.mark.parametrize("stop", ["normal", "repeated-cancel"])
# Layer: integration
async def test_api_close_settles_registered_native_command_tree(tmp_path, boundary, stop):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with app.router.lifespan_context(app):
        context = app.state.api_runtime_context
        connectors = context.outward_approval_service.connectors
        command = asyncio.create_task(connectors.invoke("run_command", {
            "command": [sys.executable, str(WORKER), str(tmp_path), "2", "detached", "ignore-term", "cancel"]}))
        context.track_background_task(command)
        processes, closing = [], None
        try:
            processes = await await_tree(tmp_path)
            closing = asyncio.create_task(context.close())
            await asyncio.sleep(0)
            if stop == "repeated-cancel":
                for _ in range(3):
                    closing.cancel()
                    await asyncio.sleep(0)
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(closing, 5)
            else:
                await asyncio.wait_for(closing, 5)
            await assert_stopped(processes, tmp_path)
            assert context.closed and command.cancelled() and context.active_background_task_count == 0
            await context.close()
        finally:
            if not processes:
                processes = await asyncio.to_thread(observe_processes, tmp_path)
            await asyncio.to_thread(stop_observed, processes)
            if not command.done():
                command.cancel()
            await asyncio.gather(command, *([closing] if closing is not None else []), return_exceptions=True)
            await context.close()


@pytest.mark.end_to_end
# Layer: end-to-end
async def test_live_tcp_api_server_finishes_application_teardown(tmp_path, boundary):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    context = None
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None, lifespan="on"))
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if serving.done():
                    await serving
                    pytest.fail("Server exited before accepting requests")
                await asyncio.sleep(0.01)
        context = app.state.api_runtime_context
        address = server.servers[0].sockets[0].getsockname()
        async with httpx.AsyncClient(base_url=f"http://{address[0]}:{address[1]}", trust_env=False) as client:
            response = await client.get("/health")
            assert response.status_code == 200 and response.json()["status"] == "ok"
        assert context.accepting_work and not context.closed
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        assert context.closed and not context.accepting_work and context.active_background_task_count == 0
        assert not await accepts_connections(address)
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 5)
        if context is not None:
            await context.close()


# Layer: integration
async def test_repeated_lifespan_cancellation_finishes_owned_teardown(tmp_path, boundary):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    context = None
    resource, address = await listener()
    started, finish = asyncio.Event(), asyncio.Event()

    async def serve():
        nonlocal context
        async with app.router.lifespan_context(app):
            context = app.state.api_runtime_context
            context.register_owned_resource(resource)
            started.set()
            await finish.wait()

    task = asyncio.create_task(serve())
    try:
        await asyncio.wait_for(started.wait(), 10)
        assert await accepts_connections(address)
        task.cancel()
        await asyncio.wait_for(resource.entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        resource.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert not await accepts_connections(address), "Lifespan returned before the owned listener closed"
        assert context.closed and context.active_background_task_count == 0
    finally:
        finish.set()
        resource.release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        resource.server.close()
        await resource.server.wait_closed()
        if context is not None:
            await context.close()
            await context.engine.close()
