"""An internal timeout cannot stand in for the API owner's cancellation request."""
from __future__ import annotations

import asyncio

import pytest

from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_api_shutdown_ownership import accepts_connections, listener

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def internally_timing_out(entered, release, tasks):
    tasks.append(asyncio.current_task())
    try:
        async with asyncio.timeout(0):
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                entered.set()
                await release.wait()
                raise
    except TimeoutError:
        await asyncio.sleep(60)


@pytest.mark.parametrize("owner", ["background-close", "request-close", "request-disconnect"])
# Layer: integration
async def test_api_owner_cancels_independently_of_inflight_internal_timeout(tmp_path, boundary, owner):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with app.router.lifespan_context(app):
        context = app.state.api_runtime_context
        resource, address = await listener()
        resource.release.set()
        context.register_owned_resource(resource)
        entered, release = asyncio.Event(), asyncio.Event()
        owned = []

        async def invoke():
            await internally_timing_out(entered, release, owned)

        if owner == "background-close":
            operation = asyncio.create_task(invoke())
            context.track_background_task(operation)
        else:
            operation = asyncio.create_task(context.run_request(invoke))
        closing = None
        try:
            await asyncio.wait_for(entered.wait(), 2)
            assert len(owned) == 1 and owned[0].cancelling() == 1
            if owner == "request-disconnect":
                operation.cancel()
                await asyncio.sleep(0)
            else:
                closing = asyncio.create_task(context.close())
                await asyncio.sleep(0)
                assert not context.accepting_work
                await asyncio.sleep(0)
            release.set()
            if owner == "request-disconnect":
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(asyncio.shield(operation), 2)
                await context.close()
            else:
                await asyncio.wait_for(asyncio.shield(closing), 2)
            assert context.closed and owned[0].done()
            assert not await accepts_connections(address)
        finally:
            release.set()
            for task in owned:
                task.cancel()
            await asyncio.gather(operation, *([closing] if closing else []), return_exceptions=True)
            await context.close()
