"""Integration: native WebSocket disconnect settles the public interaction request."""
import asyncio
import json

import pytest
from websockets.asyncio.client import connect

from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_api_interaction_lifetime import build_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("complete_turn", [False, True], ids=["idle", "completed"])
async def test_disconnected_interaction_releases_request_before_shutdown(tmp_path, monkeypatch, complete_turn):
    app = build_app(tmp_path, monkeypatch)
    async with serving_api(app) as client:
        runtime = app.state.api_runtime_context
        try:
            session = (await client.post("/v1/interactions/sessions", json={})).json()["session_id"]
            url = str(client.base_url).rstrip("/").replace("http:", "ws:") + "/ws/interactions/" + session
            async with connect(url, additional_headers={"X-API-Key": TEST_API_KEY}) as websocket:
                if complete_turn:
                    response = await client.post(f"/v1/interactions/{session}/turns", json={
                        "workload_id": "stream_test_v1", "input_config": {"seed": 7},
                    })
                    assert response.status_code == 200
                    async with asyncio.timeout(5):
                        while json.loads(await websocket.recv())["event_type"] != "commit_final":
                            pass
                assert runtime.active_request_count == 1
            async with asyncio.timeout(3):
                while runtime.active_request_count:  # noqa: ASYNC110 - public count has no settlement notification.
                    await asyncio.sleep(0.01)
        except BaseException:
            # Failure cleanup only: pre-fix idle requests otherwise also hang server exit.
            await runtime.close()
            raise
    assert runtime.closed and runtime.active_request_count == runtime.active_background_task_count == 0
