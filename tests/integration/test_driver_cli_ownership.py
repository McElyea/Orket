"""Interactive construction, native input and required transport close stay owned."""
import asyncio
import builtins
import os
import sys
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

import orket.driver as driver_module
import orket.interfaces.cli as cli_module
from orket.adapters.llm.local_model_provider import LocalModelProvider
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_cli_runtime_io_ownership import held_call
from tests.integration.test_model_selection_consumers import _environment

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def install_driver_boundaries(monkeypatch, root, state, stage, stop):
    original_init = driver_module.OrketDriver.__init__
    original_close = LocalModelProvider.close

    def construct(self, *args, **kwargs):
        if stage == "construction" and stop == "worker_failure":
            return held_call(state, root, lambda: None, failure=True)
        original_init(self, *args, **kwargs)
        state.drivers.append(self)
        if stage == "construction":
            held_call(state, root, lambda: None, failure=False)

    async def close(self):
        if stage == "close":
            stream = await asyncio.to_thread((root / "model/core/epics/publication_epic.json").open, "rb")
            state.files.append(stream)
            state.entered.set()
            try:
                assert await asyncio.to_thread(state.release.wait, 5)
                await original_close(self)
                if stop == "worker_failure":
                    raise OSError("Injected transport-close failure")
            finally:
                await asyncio.to_thread(stream.close)
                state.finished.set()
        else:
            await original_close(self)

    def read_input(_prompt):
        if stage != "input":
            return "quit"
        try:
            state.entered.set()
            value = state.reader.readline()
            if stop == "worker_failure":
                (root / "missing-driver-input").read_bytes()
            if not value:
                raise EOFError
            return value.rstrip("\r\n")
        finally:
            state.finished.set()

    monkeypatch.setattr(driver_module.OrketDriver, "__init__", construct)
    monkeypatch.setattr(LocalModelProvider, "close", close)
    monkeypatch.setattr(builtins, "input", read_input)


def release_driver_probe(state):
    state.release.set()
    with state.write_lock:
        if not state.released_pipe:
            state.writer.write("quit\n")
            state.writer.flush()
            state.released_pipe = True


@pytest.mark.parametrize("stage", ["construction", "input", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_interactive_driver_keeps_admitted_work_and_closes_transport(
    test_root, workspace, monkeypatch, record_property, stage, stop,
):
    await asyncio.to_thread(_write_epic_assets, test_root, "publication_epic")
    read_fd, write_fd = os.pipe()
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        files=[], drivers=[], reader=os.fdopen(read_fd), writer=os.fdopen(write_fd, "w"),
        write_lock=threading.Lock(), released_pipe=False)
    monkeypatch.chdir(test_root)
    for key, value in _environment("http://127.0.0.1:1/v1").items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(cli_module, "sys", SimpleNamespace(platform="fixture", stdout=sys.stdout, stderr=sys.stderr))
    monkeypatch.setattr(cli_module, "perform_first_run_setup", lambda: {"reconciliation": "success", "onboarding": "no_op"})
    monkeypatch.setattr(cli_module, "print_orket_manifest", lambda _department: None)
    install_driver_boundaries(monkeypatch, test_root, state, stage, stop)

    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await cli_module.run_cli(["--workspace", str(workspace)])

    timer = threading.Timer(.8, release_driver_probe, args=(state,))
    timer.start()
    task = asyncio.create_task(invoke())
    started = time.perf_counter()
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    await task
                    pytest.fail("CLI exited before driver boundary admission")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
        async with aiosqlite.connect(workspace / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        if stop != "timeout":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not state.finished.is_set()
        assert all(not owner.provider.client.is_closed for owner in state.drivers)
        release_driver_probe(state)
        assert await asyncio.wait_for(task, 5) == (1 if stop == "worker_failure" else 130)
        assert all(owner.provider.client.is_closed for owner in state.drivers)
    finally:
        release_driver_probe(state)
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5) or stage == "close"
        for owner in state.drivers:
            await owner.provider.client.aclose()
        await asyncio.to_thread(state.reader.close)
        await asyncio.to_thread(state.writer.close)
    assert not timer.is_alive() and all(stream.closed for stream in state.files)
