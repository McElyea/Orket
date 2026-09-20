"""Real API owners retain startup and report the effective authentication posture."""
# Layer: integration
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager, suppress

import httpx
import pytest

from orket.application.services import api_startup_service
from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.logging import event_subscriber_count, log_event, subscribe_to_events, unsubscribe_from_events
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_active_request_ownership import serving_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
RESPONSIVENESS_SECONDS = 0.5


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    return create_api_app(CompositionConfig(project_root=tmp_path))


@asynccontextmanager
async def _event_socket(app):
    """Exercise the actual ASGI WebSocket endpoint with bounded transport queues."""
    incoming, outgoing = asyncio.Queue(), asyncio.Queue()
    scope = {"type": "websocket", "path": "/ws/events", "root_path": "", "scheme": "ws",
             "query_string": b"", "headers": [(b"x-api-key", TEST_API_KEY.encode())],
             "server": ("test", 80), "client": ("test", 1), "subprotocols": [],
             "asgi": {"version": "3.0", "spec_version": "2.3"}}
    connection = asyncio.create_task(app(scope, incoming.get, outgoing.put))
    await incoming.put({"type": "websocket.connect"})
    try:
        assert (await asyncio.wait_for(outgoing.get(), 3))["type"] == "websocket.accept"
        yield outgoing
    finally:
        await incoming.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(connection, 3)


async def test_immediate_lifespan_exit_settles_admitted_broadcaster(tmp_path, monkeypatch):
    baseline = event_subscriber_count()
    for index in range(3):
        app = _app(tmp_path / str(index), monkeypatch)
        async with app.router.lifespan_context(app):
            owner = app.state.api_runtime_context
            assert event_subscriber_count() == baseline + 1
        assert owner.closed and owner.active_background_task_count == 0
        assert event_subscriber_count() == baseline


async def test_close_waits_for_admitted_initialization_cleanup(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    owner = None
    started, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    initialize, close = OrchestrationEngine.initialize, OrchestrationEngine.close
    closed = []

    async def initialize_then_hold(engine):
        await initialize(engine)
        started.set()
        try:
            await release.wait()
        finally:
            cleanup.set()
            await release.wait()

    async def close_then_record(engine):
        await close(engine)
        closed.append(True)

    async def enter_lifespan():
        async with app.router.lifespan_context(app):
            await asyncio.Event().wait()

    monkeypatch.setattr(OrchestrationEngine, "initialize", initialize_then_hold)
    monkeypatch.setattr(OrchestrationEngine, "close", close_then_record)
    starting = asyncio.create_task(enter_lifespan())
    closing = None
    try:
        await asyncio.wait_for(started.wait(), 10)
        owner = app.state.api_runtime_context
        closing = asyncio.create_task(owner.close())
        # Retain the observation and settle both tasks before asserting a timeout failure.
        with suppress(TimeoutError):
            await asyncio.wait_for(cleanup.wait(), RESPONSIVENESS_SECONDS)
        observed = (cleanup.is_set(), closing.done(), owner.closed, bool(closed))
    finally:
        release.set()
        starting.cancel()
        await asyncio.gather(starting, return_exceptions=True)
        if closing is not None:
            await asyncio.gather(closing, return_exceptions=True)
        if owner is not None:
            await owner.close()
    assert observed == (True, False, False, False)
    assert owner.closed and closed == [True] and owner.active_request_count == 0


async def test_startup_warning_matches_authenticated_tcp_policy(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "1")
    monkeypatch.setenv("ORKET_API_SECURITY_PROFILE", "local")
    monkeypatch.setenv("ORKET_ENV", "local")
    app = _app(tmp_path, monkeypatch)
    records = []
    subscribe_to_events(records.append)
    try:
        async with serving_api(app) as client:
            response = await client.get("/v1/system/runtime-policy", headers={"X-API-Key": "wrong"})
            assert response.status_code == 403
            assert (await client.get("/v1/system/runtime-policy", headers={"X-API-Key": ""})).status_code == 403
            assert (await client.get("/v1/system/runtime-policy")).status_code == 200
    finally:
        unsubscribe_from_events(records.append)
    posture = next(record["data"] for record in records if record["event"] == "api_security_posture")
    assert posture["api_key_configured"] is True
    assert posture["insecure_no_api_key_bypass"] is False
    assert not any(record["event"] == "api_security_warning" for record in records)
    assert not any("authentication is disabled" in str(getattr(record, "warning", "")) for record in caplog.records)


async def test_broadcaster_failure_stops_http_admission_and_remains_a_close_failure(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    baseline, observed = event_subscriber_count(), {}
    settled = asyncio.Event()
    start_background = ApiRuntimeContainer.start_background

    def observe_start(owner, invoke):
        task = start_background(owner, invoke)
        task.add_done_callback(lambda _task: settled.set())
        return task

    monkeypatch.setattr(ApiRuntimeContainer, "start_background", observe_start)
    with pytest.raises(RuntimeError, match="teardown failed") as failed_close:
        async with app.router.lifespan_context(app), _event_socket(app):
            owner = app.state.api_runtime_context
            # The logging API accepts arbitrary data; WebSocket JSON serialization
            # genuinely raises on this set after the real subscription receives it.
            log_event("startup-broadcast-failure", {"unsupported_json": {1}}, tmp_path)
            await asyncio.wait_for(settled.wait(), 3)
            observed["admission_closed"] = not owner.accepting_work
            await asyncio.wait_for(owner.runtime_state.event_queue.join(), RESPONSIVENESS_SECONDS)
            observed["queue_released"] = True
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                observed["health_status"] = (await client.get("/health")).status_code
    assert observed == {"admission_closed": True, "queue_released": True, "health_status": 503}
    assert isinstance(failed_close.value.__cause__, TypeError)
    assert not owner.closed and owner.active_background_task_count == owner.active_request_count == 0
    assert event_subscriber_count() == baseline


async def test_cancelled_root_observation_drains_worker_and_keeps_peer_responsive(tmp_path, monkeypatch):
    app, peer = _app(tmp_path / "first", monkeypatch), _app(tmp_path / "peer", monkeypatch)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    validate = api_startup_service._validate_root

    def held_validation(configured_root, owned_root):
        if owned_root == tmp_path / "first":
            entered.set()
            assert release.wait(5)
        validate(configured_root, owned_root)
        if owned_root == tmp_path / "first":
            finished.set()

    async def enter_lifespan():
        async with app.router.lifespan_context(app):
            pytest.fail("Canceled startup reached service admission")

    monkeypatch.setattr(api_startup_service, "_validate_root", held_validation)
    starting = asyncio.create_task(enter_lifespan())
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        owner = app.state.api_runtime_context
        starting.cancel()
        await asyncio.sleep(0)
        starting.cancel()
        assert not starting.done() and not owner.closed and not finished.is_set()
        async with (
            peer.router.lifespan_context(peer),
            httpx.AsyncClient(transport=httpx.ASGITransport(peer), base_url="http://peer") as client,
        ):
            assert (await asyncio.wait_for(client.get("/health"), RESPONSIVENESS_SECONDS)).status_code == 200
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await starting
        if (owner := getattr(app.state, "api_runtime_context", None)) is not None:
            await owner.close()
    assert finished.is_set() and owner.closed and peer.state.api_runtime_context.closed
