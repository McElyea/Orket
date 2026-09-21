"""Actual API observations refuse directory aliases and replay paths outside their roots."""
import asyncio
import json
import os
from contextlib import asynccontextmanager

import httpx
import pytest

from orket.interfaces.api import create_api_app
from tests.integration.test_api_run_observation_ownership import ROUTES

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def directory_alias(alias, target, fixture_root):
    assert alias.parent.resolve().is_relative_to(fixture_root.resolve())
    await asyncio.to_thread(alias.parent.mkdir, parents=True, exist_ok=True)
    if os.name == "nt":
        child = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command",
            "New-Item -ItemType Junction -Path $env:ORKET_TEST_LINK -Target $env:ORKET_TEST_TARGET | Out-Null",
            env={**os.environ, "ORKET_TEST_LINK": str(alias), "ORKET_TEST_TARGET": str(target)},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(child.communicate(), 15)
            assert child.returncode == 0, (stdout, stderr)
        finally:
            if child.returncode is None:
                child.kill()
                await child.communicate()
    else:
        await asyncio.to_thread(alias.symlink_to, target, target_is_directory=True)
    try:
        yield
    finally:
        await asyncio.to_thread(alias.rmdir if os.name == "nt" else alias.unlink)


async def start_session(app):
    await app.state.api_runtime_context.engine.sessions.start_session(
        "OBS", {"type": "epic", "name": "Observation", "department": "core", "task_input": "probe"},
    )


@pytest.mark.parametrize("directory", ["default", "runs"])
@pytest.mark.parametrize("kind", ["logs", "tokens", "replay-list", "graph"])
async def test_api_run_logs_reject_external_directory_alias(tmp_path, directory, kind):
    root, outside = tmp_path / "project", tmp_path / "external"
    app = create_api_app(project_root=root, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        await start_session(app)
        log = outside / ("OBS/orket.log" if directory == "runs" else "orket.log")
        await asyncio.to_thread(log.parent.mkdir, parents=True)
        content = json.dumps({"event": "turn_complete", "data": {"runtime_event": {
            "session_id": "OBS", "issue_id": "external-marker", "tokens": 7}}})
        await asyncio.to_thread(log.write_text, content, encoding="utf-8")
        alias = root / "workspace" / directory
        async with directory_alias(alias, outside, tmp_path):
            response = await client.get(ROUTES[kind])
            assert response.status_code == 400, response.text
        assert await asyncio.to_thread(log.read_text, encoding="utf-8") == content


@pytest.mark.parametrize("escape", ["issue-traversal", "turn-alias", "observability-alias", "workspace-alias"])
async def test_api_targeted_replay_rejects_external_artifacts(tmp_path, escape):
    root, outside = tmp_path / "project", tmp_path / "external"
    app = create_api_app(project_root=root, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        await start_session(app)
        observability = app.state.api_runtime_context.engine.workspace_root / "observability"
        if escape == "workspace-alias":
            checkpoint = outside / "observability/OBS/ISS/001_coder/checkpoint.json"
        elif escape == "observability-alias":
            checkpoint = outside / "OBS/ISS/001_coder/checkpoint.json"
        else:
            checkpoint = outside / "001_coder/checkpoint.json"
        await asyncio.to_thread(checkpoint.parent.mkdir, parents=True)
        await asyncio.to_thread(checkpoint.write_text, '{"external-marker":true}', encoding="utf-8")
        params = {"issue_id": "ISS", "turn_index": 1, "role": "coder"}
        if escape == "issue-traversal":
            await asyncio.to_thread((observability / "OBS").mkdir, parents=True)
            params["issue_id"] = await asyncio.to_thread(os.path.relpath, outside, observability / "OBS")
            response = await client.get("/v1/sessions/OBS/replay", params=params)
        else:
            aliases = {"workspace-alias": observability.parent, "observability-alias": observability,
                       "turn-alias": observability / "OBS/ISS/001_coder"}
            alias = aliases[escape]
            target = checkpoint.parent if escape == "turn-alias" else outside
            async with directory_alias(alias, target, tmp_path):
                response = await client.get("/v1/sessions/OBS/replay", params=params)
        assert response.status_code == 400, response.text
        assert await asyncio.to_thread(checkpoint.read_text, encoding="utf-8") == '{"external-marker":true}'
