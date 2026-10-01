"""Layer: end-to-end. Real outward SSE delivery and client-disconnect ownership."""

from __future__ import annotations

import asyncio
import json

import pytest

import orket.application.services.outward_model_tool_call_service as model_module
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import boundary as boundary
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_outward_run_admission import submission

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]


async def _read_sse_frame(lines):
    event, data = await anext(lines), await anext(lines)
    assert await anext(lines) == ""
    assert event.startswith("event: ") and data.startswith("data: ")
    return event.removeprefix("event: "), json.loads(data.removeprefix("data: "))


async def _await_request_release(context):
    async with asyncio.timeout(10):
        await asyncio.gather(*(asyncio.shield(task) for task in tuple(context._request_tasks)))
        await asyncio.sleep(0)  # Let the request wrappers release their settled owners.
    assert not context._request_tasks
    assert context.active_request_count == 0


async def test_active_outward_stream_disconnect_releases_request(tmp_path, boundary, monkeypatch):
    provider_attempts = []

    def forbid_provider(**_):
        provider_attempts.append("attempted")
        raise AssertionError("A queued run without workload steps must not construct a provider")

    monkeypatch.setattr(model_module, "create_configured_model_client", forbid_provider)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    run_id = "active-inspection-stream"
    async with serving_api(app) as client:
        context = app.state.api_runtime_context
        submitted = await client.post("/v1/runs", json=submission(run_id))
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "queued"
        before = await client.get(f"/v1/runs/{run_id}/events")
        assert before.status_code == 200, before.text
        expected_events = before.json()["events"]
        assert [event["event_type"] for event in expected_events] == ["run_submitted"]
        await _await_request_release(context)
        background_count = context.active_background_task_count

        async with client.stream("GET", f"/v1/runs/{run_id}/events/stream") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async with asyncio.timeout(10):
                lines = response.aiter_lines()
                frames = [await _read_sse_frame(lines) for _ in range(3)]
            assert frames == [("run_event", expected_events[0]), ("heartbeat", {}), ("heartbeat", {})]
            assert context.active_request_count == 1
            request_owner, = tuple(context._request_tasks)
            assert not request_owner.done()

        # Exiting the HTTP stream disconnects the client while the server stays live.
        await _await_request_release(context)
        assert request_owner.done() and request_owner not in context._request_tasks
        assert context.accepting_work and not context.closed
        assert context.active_background_task_count == background_count
        status = await client.get(f"/v1/runs/{run_id}")
        assert status.status_code == 200 and status.json()["status"] == "queued"
        after = await client.get(f"/v1/runs/{run_id}/events")
        assert after.status_code == 200 and after.json() == before.json()
        assert provider_attempts == []

    assert context.closed
    assert context.active_request_count == context.active_background_task_count == 0
