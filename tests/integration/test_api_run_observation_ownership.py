"""Authenticated runtime observations retain actual native reads through interruption."""
import asyncio
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import httpx
import pytest

from orket.interfaces.api import create_api_app

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROUTES = {
    "logs": "/v1/logs?session_id=OBS",
    "tokens": "/v1/runs/OBS/token-summary",
    "replay-list": "/v1/runs/OBS/replay",
    "graph": "/v1/runs/OBS/execution-graph",
    "targeted-replay": "/v1/sessions/OBS/replay?issue_id=ISS&turn_index=1&role=coder",
}


async def seed_observations(app, root):
    engine = app.state.api_runtime_context.engine
    await engine.sessions.start_session(
        "OBS", {"type": "epic", "name": "Observation", "department": "core", "task_input": "probe"},
    )
    log = root / "workspace/default/orket.log"
    await asyncio.to_thread(log.parent.mkdir, parents=True, exist_ok=True)
    row = {"event": "turn_complete", "role": "coder", "data": {"runtime_event": {
        "session_id": "OBS", "issue_id": "ISS", "turn_index": 1, "tokens": {"total_tokens": 7}}}}
    await asyncio.to_thread(log.write_text, json.dumps(row), encoding="utf-8")
    checkpoint = engine.workspace_root / "observability/OBS/ISS/001_coder/checkpoint.json"
    await asyncio.to_thread(checkpoint.parent.mkdir, parents=True)
    await asyncio.to_thread(checkpoint.write_text, "{}", encoding="utf-8")
    return log, checkpoint


def hold_native_read(monkeypatch, selected, failure):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), files=[])
    original = Path.read_text

    def held(path, *args, **kwargs):
        if path != selected:
            return original(path, *args, **kwargs)
        try:
            with path.open("rb") as stream:
                state.files.append(stream)
                assert stream.read(1) == b"{"
                state.entered.set()
                assert state.release.wait(5), "Native observation read release deadline"
                if failure:
                    raise OSError("Injected native observation read failure")
                return original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "read_text", held)
    return state


@pytest.mark.parametrize("kind", list(ROUTES))
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_api_run_observations_are_responsive_and_owned(tmp_path, monkeypatch, record_property, kind, stop):
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        log, checkpoint = await seed_observations(app, tmp_path)
        state = hold_native_read(monkeypatch, checkpoint if kind == "targeted-replay" else log, stop == "worker_failure")

        async def invoke():
            async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
                state.deadline = deadline
                return await client.get(ROUTES[kind])

        timer = threading.Timer(.8, state.release.set)
        timer.start()
        started = time.perf_counter()
        request = asyncio.create_task(invoke())
        try:
            async with asyncio.timeout(5):
                while not state.entered.is_set():
                    if request.done():
                        pytest.fail(f"Request ended before native read: {await request}")
                    await asyncio.sleep(.001)
            if stop == "timeout":
                state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
            async with aiosqlite.connect(tmp_path / "responsive.sqlite3") as connection:
                assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
            elapsed = time.perf_counter() - started
            record_property("responsive_sqlite_seconds", elapsed)
            assert elapsed < .5
            assert (await client.get("/v1/system/heartbeat")).status_code == 200
            if stop != "timeout":
                request.cancel()
                await asyncio.sleep(0)
                request.cancel()
            await asyncio.sleep(.08)
            assert not request.done() and not state.finished.is_set() and not state.files[0].closed
            assert app.state.api_runtime_context.active_request_count == 1
            state.release.set()
            expected = OSError if stop == "worker_failure" else TimeoutError if stop == "timeout" else asyncio.CancelledError
            with pytest.raises(expected):
                await asyncio.wait_for(request, 5)
        finally:
            state.release.set()
            timer.cancel()
            await asyncio.to_thread(timer.join, 5)
            await asyncio.gather(request, return_exceptions=True)
            assert await asyncio.to_thread(state.finished.wait, 5)
        assert not timer.is_alive() and all(stream.closed for stream in state.files)
        assert app.state.api_runtime_context.active_request_count == 0
