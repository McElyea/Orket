"""Layer: integration. Observe actual ASGI WebSockets and streaming HTTP shutdown."""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_api_active_request_ownership import serving_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("channel", ["events", "interactions"])
# Layer: integration
async def test_actual_websocket_routes_close_and_release_subscriptions(tmp_path, boundary, monkeypatch, channel):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")

    def exercise():
        app = create_api_app(CompositionConfig(project_root=tmp_path))
        with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
            context = app.state.api_runtime_context
            path = "/ws/events"
            if channel == "interactions":
                response = client.post("/v1/interactions/sessions", json={"session_params": {}})
                assert response.status_code == 200
                path = "/ws/interactions/" + response.json()["session_id"]
            with client.websocket_connect(path, headers={"X-API-Key": TEST_API_KEY}) as socket:
                assert context.active_request_count == 1
                client.portal.call(context.close)
                assert socket.receive() == {"type": "websocket.close", "code": 1001}
            assert context.closed and context.active_request_count == 0
            assert client.portal.call(context.runtime_state.get_websockets) == []
            assert client.get("/health").status_code == 503
            with client.websocket_connect(path, headers={"X-API-Key": TEST_API_KEY}) as socket:
                pytest.fail("Closed API accepted a new WebSocket")

    # TestClient rejects a pre-accept close as WebSocketDisconnect.
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as rejected:
        await asyncio.to_thread(exercise)
    assert rejected.value.code == 1001


# Layer: integration
async def test_streaming_body_remains_owned_after_response_headers(tmp_path, boundary):
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    stopped = asyncio.Event()

    async def body():
        try:
            yield b"started\n"
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def stream():
        return StreamingResponse(body(), media_type="text/plain")

    app.add_api_route("/v1/ownership-stream", stream, methods=["GET"])
    async with serving_api(app) as client, client.stream("GET", "/v1/ownership-stream") as response:
        context = app.state.api_runtime_context
        assert response.status_code == 200 and "X-Orket-Version" in response.headers
        chunks = response.aiter_lines()
        assert await anext(chunks) == "started"
        assert context.active_request_count == 1
        await asyncio.wait_for(context.close(), 5)
        assert stopped.is_set() and context.closed and context.active_request_count == 0
        with pytest.raises(httpx.RemoteProtocolError):
            await anext(chunks)
