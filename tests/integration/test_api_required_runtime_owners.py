"""Integration: incomplete API ownership refuses admission and retains cleanup."""
import asyncio

import httpx
import pytest

from orket.application.services import api_runtime_preparation
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.logging import event_subscriber_count
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_missing_authentication_refuses_startup_and_closes_native_owners(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    build = api_runtime_preparation.build_api_runtime_container
    observed = []
    subscribers = event_subscriber_count()

    def incomplete(*args, **kwargs):
        owner = build(*args, **kwargs)
        owner.authentication = None
        observed.append(owner)
        return owner

    monkeypatch.setattr(api_runtime_preparation, "build_api_runtime_container", incomplete)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    with pytest.raises(RuntimeError, match="API authentication is not configured"):
        async with app.router.lifespan_context(app):
            pytest.fail("Incomplete authentication admitted startup")
    owner, = observed
    assert owner.closed and owner.active_request_count == owner.active_background_task_count == 0
    assert event_subscriber_count() == subscribers
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as client:
        assert (await client.get("/health")).status_code == 503


@pytest.mark.parametrize("operation", ["start", "cancel"])
async def test_missing_interaction_owner_refuses_http_work_without_durable_action(tmp_path, monkeypatch, operation):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    async with app.router.lifespan_context(app):
        owner = app.state.api_runtime_context
        manager = owner.interaction_manager
        session = await manager.start({})
        status = await manager.queries.get_session_status(session)
        owner.interaction_manager = None
        try:
            path = "/v1/interactions/sessions" if operation == "start" else f"/v1/interactions/{session}/cancel"
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture",
                                        headers={"X-API-Key": TEST_API_KEY}) as client:
                with pytest.raises(RuntimeError, match="API interaction manager is not configured"):
                    await asyncio.wait_for(client.post(path, json={}), 5)
            assert await manager.queries.get_session_status(session) == status
            assert await owner.engine.control_plane_repository.list_operator_actions(
                target_ref=f"interaction-session:{session}") == []
            assert owner.active_request_count == 0
        finally:
            owner.interaction_manager = manager
    assert owner.closed
