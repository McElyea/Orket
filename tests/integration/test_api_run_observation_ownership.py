"""Authenticated runtime observations retain actual native reads through interruption."""
import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from orket.interfaces.api import create_api_app
from tests.helpers.api_observation_lifetime import exercise_owned_api_read

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

        await exercise_owned_api_read(app, client, ROUTES[kind], state, tmp_path, record_property, stop)
