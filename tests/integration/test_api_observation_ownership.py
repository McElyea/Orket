"""Layer: integration. API observations own real workers and captured request inputs."""
import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack

import httpx
import pytest

from orket import hardware
from orket import logging as event_adapter
from orket.application.services.api_event_service import ApiEventService
from orket.interfaces.api import create_api_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_SECONDS = 0.5
SETTLEMENT_SECONDS = 3


async def _request(app, path, key="expected"):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        return await client.get(path, headers={"X-API-Key": key})


@pytest.mark.parametrize("stop", ["cancel", "timeout", "shutdown"])
async def test_metrics_request_retains_real_worker_until_settled(tmp_path, monkeypatch, stop):
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = hardware._cached_vram_metrics

    def held_metrics(ttl):
        result = original(ttl)
        entered.set()
        try:
            assert release.wait(15), "Fixture worker was not released"
            return result
        finally:
            settled.set()

    app = create_api_app(project_root=tmp_path, environment={**os.environ, "ORKET_API_KEY": "expected"})
    async with app.router.lifespan_context(app):
        monkeypatch.setattr(hardware, "_cached_vram_metrics", held_metrics)
        owner = app.state.api_runtime_context

        async def invoke():
            if stop == "timeout":
                async with asyncio.timeout(0.2):
                    return await _request(app, "/v1/system/metrics")
            return await _request(app, "/v1/system/metrics")

        request, closing = asyncio.create_task(invoke()), None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            heartbeat = await asyncio.wait_for(_request(app, "/v1/system/heartbeat"), RESPONSIVENESS_SECONDS)
            assert heartbeat.status_code == 200
            if stop == "shutdown":
                closing = asyncio.create_task(owner.close())
            elif stop == "cancel":
                request.cancel()
                await asyncio.sleep(0)
                request.cancel()
            await asyncio.sleep(0.25 if stop == "timeout" else 0.05)
            assert not request.done(), "Request escaped while its hardware worker was still running"
            if closing is not None:
                assert not closing.done() and not owner.closed
            release.set()
            result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            assert settled.is_set()
            if stop == "timeout":
                assert isinstance(result, TimeoutError)
            elif stop == "cancel":
                assert isinstance(result, asyncio.CancelledError)
            else:
                assert result.status_code == 503
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            if closing is not None:
                await asyncio.wait_for(closing, SETTLEMENT_SECONDS)
            await owner.close()
            assert await asyncio.to_thread(settled.wait, SETTLEMENT_SECONDS)


@pytest.mark.parametrize("stop", ["cancel", "timeout", "shutdown"])
async def test_rejected_auth_retains_its_event_write(tmp_path, monkeypatch, stop):
    entered, release = threading.Event(), threading.Event()
    original = event_adapter._append_line_sync

    def held_write(path, line):
        entered.set()
        assert release.wait(15), "Fixture write was not released"
        original(path, line)

    app = create_api_app(project_root=tmp_path, environment={**os.environ, "ORKET_API_KEY": "expected"})
    async with app.router.lifespan_context(app):
        monkeypatch.setattr(event_adapter, "_append_line_sync", held_write)
        owner = app.state.api_runtime_context

        async def invoke():
            if stop == "timeout":
                async with asyncio.timeout(0.2):
                    return await _request(app, "/v1/system/heartbeat", key="wrong")
            return await _request(app, "/v1/system/heartbeat", key="wrong")

        request, closing = asyncio.create_task(invoke()), None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            response = await asyncio.wait_for(_request(app, "/v1/system/heartbeat"), RESPONSIVENESS_SECONDS)
            assert response.status_code == 200
            if stop == "shutdown":
                closing = asyncio.create_task(owner.close())
            elif stop == "cancel":
                request.cancel()
                await asyncio.sleep(0)
                request.cancel()
            await asyncio.sleep(0.25 if stop == "timeout" else 0.05)
            assert not request.done()
            if closing is not None:
                assert not closing.done() and not owner.closed
            release.set()
            await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            records = [json.loads(line) for line in (await asyncio.to_thread(
                (tmp_path / "orket.log").read_text, encoding="utf-8")).splitlines()]
            assert [item["event"] for item in records] == ["api_security_posture", "api_auth_rejected"]
            record = records[-1]
            assert record["event"] == "api_auth_rejected"
            assert record["data"]["request_path"] == "/v1/system/heartbeat"
            assert "wrong" not in json.dumps(record)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), SETTLEMENT_SECONDS)
            if closing is not None:
                await asyncio.wait_for(closing, SETTLEMENT_SECONDS)
            await owner.close()


async def test_event_worker_captures_nested_payload_before_await(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = event_adapter.log_event

    def held_event(*args):
        entered.set()
        assert release.wait(15), "Fixture event was not released"
        original(*args)

    monkeypatch.setattr("orket.application.services.api_event_service.log_event", held_event)
    payload = {"nested": {"values": ["admitted"]}}
    writing = asyncio.create_task(ApiEventService(tmp_path).emit("fixture", payload))
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        payload["nested"]["values"].append("late")
        release.set()
        await asyncio.wait_for(writing, SETTLEMENT_SECONDS)
        record = json.loads(await asyncio.to_thread((tmp_path / "orket.log").read_text, encoding="utf-8"))
        assert record["data"]["nested"] == {"values": ["admitted"]}
    finally:
        release.set()
        await asyncio.wait_for(writing, SETTLEMENT_SECONDS)


async def test_event_write_failure_is_observed_by_request(tmp_path):
    app = create_api_app(project_root=tmp_path, environment={**os.environ, "ORKET_API_KEY": "expected"})
    async with app.router.lifespan_context(app):
        await asyncio.to_thread((tmp_path / "orket.log").rename, tmp_path / "startup.log")
        await asyncio.to_thread((tmp_path / "orket.log").mkdir)
        with pytest.raises(OSError):
            await _request(app, "/v1/system/heartbeat", key="wrong")
        assert (await _request(app, "/v1/system/heartbeat")).status_code == 200


async def test_concurrent_rejections_write_only_to_their_application_roots(tmp_path):
    apps = [create_api_app(project_root=tmp_path / name, environment={**os.environ, "ORKET_API_KEY": name})
            for name in ("first", "second")]
    async with AsyncExitStack() as lifetimes:
        for app in apps:
            await lifetimes.enter_async_context(app.router.lifespan_context(app))
        responses = await asyncio.gather(*[
            _request(app, f"/v1/sessions/{index}", key="wrong") for index, app in enumerate(apps)
        ])
        assert [response.status_code for response in responses] == [403, 403]
        for index, name in enumerate(("first", "second")):
            records = (await asyncio.to_thread((tmp_path / name / "orket.log").read_text, encoding="utf-8")).splitlines()
            assert [json.loads(record)["event"] for record in records] == ["api_security_posture", "api_auth_rejected"]
            assert json.loads(records[-1])["data"]["request_path"] == f"/v1/sessions/{index}"
