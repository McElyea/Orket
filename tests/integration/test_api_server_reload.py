"""Integration: real spawned workers, file-triggered reload, TCP and retained close."""
from __future__ import annotations

import os
import re
import shutil
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psutil
import pytest

import orket
from tests.helpers.api_reload_process import owned_server, signal_server, until

pytestmark = pytest.mark.integration


def environment(project, *, controlled=False, **extra):
    source = Path(__file__).resolve().parents[2]
    script = source / ("tests/helpers/reload_lifespan_app.py" if controlled else "server.py")
    shutil.copyfile(script, project / "server.py")
    (project / "reload_trigger.py").touch()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    values = dict(os.environ, ORKET_DISABLE_SANDBOX="1", ORKET_ENV="local", ORKET_API_KEY="reload-proof",
                  ORKET_DURABLE_ROOT=str(project / ".orket/durable"),
                  ORKET_OUTWARD_PIPELINE_DB_PATH=str(project / "outward.db"),
                  PYTHONPATH=str(Path(orket.__file__).resolve().parent.parent),
                  RELOAD_TEST_PORT=str(port), **extra)
    return values, port


def health(client):
    try:
        response = client.get("/health")
        return response.json() if response.status_code == 200 else None
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return None


def server_pid(project):
    text = (project / "server.log").read_text(encoding="utf-8", errors="replace")
    pids = re.findall(r"Started server process \[(\d+)\]", text)
    return int(pids[-1]) if pids else None


def trigger_reload(project, iteration):
    # StatReload establishes its baseline only after worker creation.
    trigger = project / "reload_trigger.py"
    time.sleep(0.6)
    trigger.write_text(f"# reload iteration {iteration}\n", encoding="utf-8")


@pytest.mark.parametrize("reload", [False, True])
def test_canonical_server_tcp_and_repeated_file_reload(tmp_path, reload):
    values, port = environment(tmp_path)
    args = ["--host", "127.0.0.1", "--port", str(port), "--profile", "dev" if reload else "safe",
            "--reload" if reload else "--no-reload"]
    with owned_server(tmp_path, args, values) as process, httpx.Client(
        base_url=f"http://127.0.0.1:{port}", timeout=1, trust_env=False,
    ) as client:
        assert until(lambda: health(client))["status"] == "ok"
        assert client.get("/v1/system/heartbeat").status_code == 403
        assert client.get("/v1/system/heartbeat", headers={"X-API-Key": "reload-proof"}).status_code == 200
        for iteration in range(2 if reload else 0):
            old = psutil.Process(server_pid(tmp_path))
            trigger_reload(tmp_path, iteration)
            until(lambda old=old: server_pid(tmp_path) != old.pid and health(client))
            assert not old.is_running()
        signal_server(process, tmp_path / "server.py")
        assert process.wait(timeout=15) == 0
    log = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert log.count("Application shutdown complete.") == (3 if reload else 1)
    assert "Application shutdown failed" not in log


@pytest.mark.parametrize("phase", ["startup", "request", "shutdown"])
def test_reload_stop_drains_held_lifecycle_despite_repeated_signals(tmp_path, phase):
    values, port = environment(tmp_path, controlled=True, RELOAD_TEST_HOLD=phase)
    with owned_server(tmp_path, [], values) as process, httpx.Client(
        base_url=f"http://127.0.0.1:{port}", timeout=15, trust_env=False,
    ) as client, ThreadPoolExecutor(max_workers=1) as requests:
        request = None
        try:
            if phase != "startup":
                until(lambda: health(client))
            if phase == "request":
                request = requests.submit(client.get, "/held")
            if phase == "shutdown":
                signal_server(process, tmp_path / "server.py")
            marker, = until(lambda: list(tmp_path.glob(f"*-{phase}-held")))
            pid = int(marker.name.split("-", 1)[0])
            signal_server(process, tmp_path / "server.py")
            time.sleep(0.15)
            signal_server(process, tmp_path / "server.py")
            assert process.poll() is None and not (tmp_path / f"{pid}-closed").exists()
        finally:
            (tmp_path / "release").touch()
        if request is not None:
            assert request.result(timeout=10).status_code == 200
            assert (tmp_path / f"{pid}-request-completed").exists()
        assert process.wait(timeout=15) == 0
        assert (tmp_path / f"{pid}-closed").exists()


@pytest.mark.parametrize("phase", ["startup", "shutdown"])
def test_reload_worker_failure_fails_launcher_without_replacement(tmp_path, phase):
    values, port = environment(tmp_path, controlled=True, RELOAD_TEST_FAILURE=phase)
    with owned_server(tmp_path, [], values) as process, httpx.Client(
        base_url=f"http://127.0.0.1:{port}", timeout=1, trust_env=False,
    ) as client:
        if phase == "shutdown":
            until(lambda: health(client))
            trigger_reload(tmp_path, 1)
            until(lambda: list(tmp_path.glob("*-cleanup-failed")))
        until(lambda: process.poll() is not None, timeout=10)
        assert process.returncode != 0
    log = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert len(re.findall(r"Started server process \[(\d+)\]", log)) == 1
    assert f"controlled {'cleanup' if phase == 'shutdown' else 'startup'} failure" in log


def test_canonical_reload_startup_failure_publishes_diagnostic_and_exits(tmp_path):
    values, port = environment(tmp_path, ORKET_ALLOW_INSECURE_NO_API_KEY="1")
    values["ORKET_ENV"] = "production"
    args = ["--host", "127.0.0.1", "--port", str(port), "--profile", "dev", "--reload"]
    with owned_server(tmp_path, args, values) as process:
        assert process.wait(timeout=25) == 1
    log = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert "is forbidden" in log
    diagnostic = (tmp_path / "workspace/default/orket_crash.log").read_text(encoding="utf-8")
    assert "E_API_RELOAD_WORKER_FAILED" in diagnostic
    assert "Crash report saved:" in log
    assert "ImportError" not in log
