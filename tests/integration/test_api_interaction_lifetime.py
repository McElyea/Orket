"""Public HTTP interactions retain application adoption and native file cleanup."""
import asyncio
import json
import threading
import time
from pathlib import Path

import httpx
import pytest

from orket.adapters.storage.interaction_artifact_store import InteractionArtifactStore
from orket.application.interactions import commands
from orket.core.contracts.interaction_stream import StreamEventType
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_interaction_transition_lifetime import hold_event

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def build_app(root, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    return create_api_app(CompositionConfig(project_root=root))


async def test_real_http_adopts_workload_and_shutdown_waits_for_native_commit(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    publish = InteractionArtifactStore._publish_sync

    def held(store, session_id, turn_id, name, content):
        if name == "authority_commit.json":
            entered.set()
            assert release.wait(5)
        return publish(store, session_id, turn_id, name, content)

    monkeypatch.setattr(InteractionArtifactStore, "_publish_sync", held)
    closing = None
    async with serving_api(app) as client:
        runtime = app.state.api_runtime_context
        try:
            started = await client.post("/v1/interactions/sessions", json={"session_params": {"label": "tcp"}})
            assert started.status_code == 200
            session = started.json()["session_id"]
            response = await client.post(f"/v1/interactions/{session}/turns",
                                         json={"workload_id": "stream_test_v1", "input_config": {"seed": 7}})
            assert response.status_code == 200
            turn = response.json()["turn_id"]
            assert await asyncio.to_thread(entered.wait, 0.5)
            measured = time.monotonic()
            assert (await asyncio.wait_for(client.get("/v1/system/heartbeat"), 0.5)).status_code == 200
            assert time.monotonic() - measured < 0.5
            assert runtime.active_background_task_count >= 1
            closing = asyncio.create_task(runtime.close())
            await asyncio.sleep(0.02)
            closing.cancel()
            await asyncio.sleep(0.02)
            assert not closing.done() and not runtime.closed
            settled = time.monotonic()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(closing, 3)
            assert time.monotonic() - settled < 3
            assert runtime.closed and runtime.active_background_task_count == runtime.active_request_count == 0
            path = tmp_path / "workspace/interactions" / session / turn / "authority_commit.json"
            payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
            assert payload["authoritative"] is True
            assert payload["intents"] == [{"type": "turn_finalize", "ref": "stream_test_v1", "payload_digest": None}]
            before = await asyncio.to_thread(path.read_bytes)
            await asyncio.sleep(0.05)
            assert await asyncio.to_thread(path.read_bytes) == before
            assert await runtime.interaction_manager.queries.get_session_detail(session) is None
        finally:
            release.set()
            if closing is not None:
                await asyncio.gather(closing, return_exceptions=True)


async def test_interrupted_http_admission_has_failed_commit_and_no_unadopted_work(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        runtime = app.state.api_runtime_context
        startup_tasks = set(runtime._background_tasks)
        manager = runtime.interaction_manager
        session = await manager.start({})
        queue = await manager.bus.subscribe(session)
        entered, release = hold_event(monkeypatch, manager.bus, StreamEventType.TURN_ACCEPTED)
        request = None
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture",
                                    headers={"X-API-Key": TEST_API_KEY}) as client:
            try:
                request = asyncio.create_task(client.post(f"/v1/interactions/{session}/turns",
                                                           json={"workload_id": "stream_test_v1"}))
                await asyncio.wait_for(entered.wait(), 0.5)
                request.cancel()
                assert (await asyncio.wait_for(client.get("/v1/system/heartbeat"), 0.5)).status_code == 200
                assert not request.done()
                release.set()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(request, 3)
                assert (await manager.queries.get_session_status(session))["status"] == "idle"
                events = [queue.get_nowait() for _ in range(queue.qsize())]
                assert [event.event_type for event in events] == [StreamEventType.TURN_ACCEPTED,
                                                                StreamEventType.TURN_INTERRUPTED, StreamEventType.COMMIT_FINAL]
                assert events[-1].payload["commit_outcome"] == "fail_closed"
                path = Path(events[-1].payload["artifact_refs"][0])
                payload = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
                assert payload["intents"] == [{"type": "decision", "ref": "fail_closed:admission_interrupted",
                                               "payload_digest": None}]
                assert set(runtime._background_tasks) == startup_tasks and runtime.active_request_count == 0
            finally:
                release.set()
                if request is not None:
                    await asyncio.gather(request, return_exceptions=True)
                await manager.bus.unsubscribe(session, queue)
                await runtime.close()


async def test_public_finalize_cannot_commit_while_adopted_workload_is_still_running(tmp_path, monkeypatch):
    app = build_app(tmp_path, monkeypatch)
    async with app.router.lifespan_context(app):
        runtime = app.state.api_runtime_context
        startup_tasks = set(runtime._background_tasks)
        entered, release = asyncio.Event(), asyncio.Event()
        run = commands.run_builtin_workload

        async def held(**kwargs):
            entered.set()
            await release.wait()
            return await run(**kwargs)

        monkeypatch.setattr(commands, "run_builtin_workload", held)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture",
                                    headers={"X-API-Key": TEST_API_KEY}) as client:
            try:
                session = (await client.post("/v1/interactions/sessions", json={})).json()["session_id"]
                response = await client.post(f"/v1/interactions/{session}/turns", json={"workload_id": "stream_test_v1"})
                turn = response.json()["turn_id"]
                await asyncio.wait_for(entered.wait(), 0.5)
                refused = await client.post(f"/v1/interactions/{session}/finalize", json={"turn_id": turn})
                assert refused.status_code == 400 and "not published its result" in refused.text
                path = tmp_path / "workspace/interactions" / session / turn / "authority_commit.json"
                assert not await asyncio.to_thread(path.exists)
                with pytest.raises(ValueError, match="Drain the owning application"):
                    await runtime.interaction_manager.close(session)
                tasks = tuple(set(runtime._background_tasks) - startup_tasks)
                release.set()
                await asyncio.wait_for(asyncio.gather(*tasks), 3)
                finalized = await client.post(f"/v1/interactions/{session}/finalize", json={"turn_id": turn})
                assert finalized.status_code == 200 and finalized.json()["status"] == "committed"
                assert json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))["authoritative"]
            finally:
                release.set()
                await runtime.close()
