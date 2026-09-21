"""Actual pipeline/file/native-child lifetime for authenticated sandbox log requests."""
import asyncio
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import aiosqlite
import httpx
import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.interfaces.api import create_api_app
from tests.adapters.test_sandbox_command_runner import _sandbox

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_input_file(state, root, *, failure):
    try:
        with (root / "sandbox-log-input.txt").open("rb") as stream:
            state.files.append(stream)
            assert stream.read() == b"owned"
            state.entered.set()
            assert state.release.wait(5), "Sandbox log worker release deadline"
            if failure:
                (root / "missing-sandbox-log-input.txt").read_bytes()
    finally:
        state.finished.set()


class NativeLogRunner:
    """Controlled local command port: real process and pipes, no Docker claim."""

    def __init__(self, state, stage, failure):
        self.state, self.stage, self.failure = state, stage, failure

    def run_sync(self, *command, timeout=None):
        assert timeout == 10 and command[0] == "docker-compose"
        self.state.commands.append(command)
        code = "import sys;sys.stdin.readline();print('native sandbox logs');sys.exit(" + str(17 if self.failure else 0) + ")"
        try:
            with subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as child:
                self.state.children.append(child)
                if self.stage == "read":
                    self.state.entered.set()
                    assert self.state.release.wait(5), "Sandbox log child release deadline"
                try:
                    stdout, stderr = child.communicate("release\n", timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()
                    raise
                return CommandResult(child.returncode, stdout, stderr)
        finally:
            if self.stage == "read":
                self.state.finished.set()


def install_pipeline_probe(app, root, monkeypatch, state, stage, stop):
    host = app.state.api_runtime_context.api_runtime_host
    original = host.create_execution_pipeline

    def construct(workspace):
        if stage == "construction" and stop == "worker_failure":
            hold_input_file(state, root, failure=True)
        owner = original(workspace)
        state.owners.append(owner)
        original_close = owner.close
        state.cleanup.append(original_close)
        owner.sandbox_orchestrator.registry.register(_sandbox(workspace))
        owner.sandbox_orchestrator.command_runner = NativeLogRunner(state, stage, stage == "read" and stop == "worker_failure")

        async def close():
            try:
                if stage == "close":
                    await asyncio.to_thread(hold_input_file, state, root, failure=stop == "worker_failure")
            finally:
                await original_close()

        monkeypatch.setattr(owner, "close", close)
        if stage == "construction":
            hold_input_file(state, root, failure=False)
        return owner

    monkeypatch.setattr(host, "create_execution_pipeline", construct)


async def interrupt_request(client, context, root, state, stage, stop, record_property):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await client.get("/v1/sandboxes/sandbox-test/logs")

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    request = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if request.done():
                    pytest.fail(f"Request ended before {stage} admission: {await request}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
        async with aiosqlite.connect(root / "responsive.sqlite3") as connection:
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
        assert not request.done() and not state.finished.is_set()
        assert context.active_request_count == 1 and all(not owner._closed for owner in state.owners)
        if stage == "read":
            assert state.children and all(child.poll() is None for child in state.children)
        state.release.set()
        expected = (RuntimeError if stage == "read" else OSError) if stop == "worker_failure" else (
            TimeoutError if stop == "timeout" else asyncio.CancelledError)
        with pytest.raises(expected):
            await asyncio.wait_for(request, 5)
        assert all(owner._closed for owner in state.owners)
        if stage == "construction":
            assert state.commands == []
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(request, return_exceptions=True)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
        for close in state.cleanup:
            await close()
    assert not timer.is_alive() and all(stream.closed for stream in state.files)
    assert all(child.returncode is not None and child.stdin.closed and child.stdout.closed for child in state.children)


@pytest.mark.parametrize("stage", ["construction", "read", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_api_sandbox_logs_retain_pipeline_and_native_work(tmp_path, monkeypatch, record_property, stage, stop):
    await asyncio.to_thread((tmp_path / "sandbox-log-input.txt").write_text, "owned", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], cleanup=[], children=[], commands=[])
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        install_pipeline_probe(app, tmp_path, monkeypatch, state, stage, stop)
        await interrupt_request(client, app.state.api_runtime_context, tmp_path, state, stage, stop, record_property)


async def test_api_sandbox_logs_nonzero_command_cannot_return_success(tmp_path, monkeypatch):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], cleanup=[], children=[], commands=[])
    state.release.set()
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app, raise_app_exceptions=False),
        base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        install_pipeline_probe(app, tmp_path, monkeypatch, state, "read", "worker_failure")
        try:
            response = await client.get("/v1/sandboxes/sandbox-test/logs")
            assert response.status_code == 500, response.text
            assert state.commands and all(child.returncode == 17 for child in state.children)
            assert all(owner._closed for owner in state.owners)
        finally:
            for close in state.cleanup:
                await close()
