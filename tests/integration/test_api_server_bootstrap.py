"""Integration: a spawned server's pre-loop bootstrap supports its later ASGI import."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

import orket

pytestmark = pytest.mark.integration

PROBE = '''
import asyncio
import importlib
import json
import runpy

import httpx

from orket.settings import load_user_preferences, load_user_settings

first = runpy.run_path("server.py", run_name="__mp_main__")["app"]
assert not first.state.api_ready
assert not hasattr(first.state, "api_runtime_context")

async def observe():
    # Uvicorn imports server:app from inside its running event loop.
    app = importlib.import_module("server").app
    assert app is not first
    settings, preferences = load_user_settings(), load_user_preferences()
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://server-bootstrap",
    ) as client:
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/v1/system/heartbeat")).status_code == 403
        response = await client.get("/v1/system/heartbeat", headers={"X-API-Key": "server-bootstrap"})
        assert response.status_code == 200
    assert app.state.api_runtime_context.closed and not app.state.api_ready
    return {"settings": settings, "preferences": preferences, "closed": True}

print(json.dumps(asyncio.run(observe())))
'''


def test_canonical_server_binds_both_snapshots_before_loop_import(tmp_path):
    source = Path(__file__).resolve().parents[2] / "server.py"
    shutil.copyfile(source, tmp_path / "server.py")
    config = tmp_path / ".orket/durable/config"
    config.mkdir(parents=True)
    settings = {"protocol_timezone": "Pacific/Honolulu"}
    preferences = {"models": {"coder": "bootstrap-fixture"}}
    (config / "user_settings.json").write_text(json.dumps(settings), encoding="utf-8")
    (config / "preferences.json").write_text(json.dumps(preferences), encoding="utf-8")
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", ORKET_ENV="local",
        ORKET_API_KEY="server-bootstrap", ORKET_DURABLE_ROOT=str(tmp_path / ".orket/durable"),
        PYTHONPATH=str(Path(orket.__file__).resolve().parent.parent))
    with subprocess.Popen([sys.executable, "-c", PROBE], cwd=tmp_path, env=environment,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        owner = psutil.Process(process.pid)
        try:
            output, errors = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            children = owner.children(recursive=True)
            for child in [*reversed(children), owner]:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    continue
            output, errors = process.communicate(timeout=10)
            _, alive = psutil.wait_procs(children, timeout=10)
            assert not alive, "Bootstrap timeout cleanup left observed child processes running"
            pytest.fail(f"Server bootstrap did not settle within 30 seconds: {output}\n{errors}")
    assert process.returncode == 0, output + errors
    observed = json.loads(output.splitlines()[-1])
    assert observed["settings"] == settings and observed["closed"]
    assert observed["preferences"]["models"] == preferences["models"]
    assert observed["preferences"] == json.loads((config / "preferences.json").read_text(encoding="utf-8"))
