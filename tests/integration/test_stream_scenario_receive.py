"""Native API proof: a slow commit must survive repeated scenario poll timeouts."""
import asyncio
import json
import shutil
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from orket.application.interactions import commands
from orket.application.interactions.commit import CommitOrchestrator
from scripts.streaming import run_stream_scenario as runner
from scripts.streaming.scenario_receive import scenario_socket

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


def test_delayed_native_commit_is_not_lost_after_poll_timeouts(test_root, monkeypatch):
    shutil.copyfile(ROOT / "config/organization.json", test_root / "config/organization.json")
    monkeypatch.chdir(test_root)
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(test_root / ".orket/durable"))
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")
    monkeypatch.setenv("ORKET_API_KEY", "scenario-held-commit")
    release = threading.Event()
    start_workload = threading.Event()
    publication_held = threading.Event()
    real_workload = commands.run_builtin_workload
    real_trace = CommitOrchestrator.trace
    real_receive = runner._receive_json_with_timeout
    polls = []

    async def admitted_workload(**kwargs):
        assert await asyncio.to_thread(start_workload.wait, 10), "scenario did not begin polling"
        return await real_workload(**kwargs)

    async def held_trace(self, **kwargs):
        await real_trace(self, **kwargs)
        publication_held.set()
        assert await asyncio.to_thread(release.wait, 10), "scenario never released held publication"

    def observe_poll(socket, timeout):
        start_workload.set()  # The scenario's early explicit-finalize request has returned.
        event = real_receive(socket, timeout)
        if event is None and publication_held.is_set():
            polls.append(None)
            if len(polls) == 2:
                release.set()
        return event

    monkeypatch.setattr(CommitOrchestrator, "trace", held_trace)
    monkeypatch.setattr(commands, "run_builtin_workload", admitted_workload)
    monkeypatch.setattr(runner, "_receive_json_with_timeout", observe_poll)
    try:
        verdict = runner.run_scenario(
            scenario_path=ROOT / "docs/observability/stream_scenarios/s6_finalize_cancel_noop.yaml", timeout_s=4,
        )
    finally:
        start_workload.set()
        release.set()
    commit = test_root / "workspace/interactions" / verdict["session_id"] / verdict["turn_id"] / "authority_commit.json"
    assert json.loads(commit.read_text())["authoritative"] is True
    assert len(polls) >= 2
    assert verdict["status"] == "PASS"
    assert verdict["commit_outcome"] == "ok"
    assert not any(t.name.startswith("orket-scenario-receive") for t in threading.enumerate())


def test_quiet_socket_keeps_one_reader_and_settles_on_context_exit():
    app = FastAPI()

    @app.websocket("/quiet")
    async def quiet(socket: WebSocket):
        await socket.accept()
        await socket.receive()

    with TestClient(app) as client:
        with scenario_socket(client.websocket_connect("/quiet")) as receiver:
            for _ in range(3):
                assert receiver.receive(0.02) is None
            readers = [t for t in threading.enumerate() if t.name == "orket-scenario-receive"]
            assert len(readers) == 1
        assert not readers[0].is_alive()


@pytest.mark.parametrize("mode", ["disconnect", "invalid_json"])
def test_native_transport_failure_is_reported_and_reader_settles(mode):
    app = FastAPI()

    @app.websocket("/failure")
    async def failure(socket: WebSocket):
        await socket.accept()
        if mode == "disconnect":
            await socket.close(code=1011)
        else:
            await socket.send_text("invalid JSON")

    expected = WebSocketDisconnect if mode == "disconnect" else json.JSONDecodeError
    with (
        TestClient(app) as client,
        scenario_socket(client.websocket_connect("/failure")) as receiver,
        pytest.raises(expected),
    ):
        receiver.receive(2)
    assert not any(t.name == "orket-scenario-receive" for t in threading.enumerate())
