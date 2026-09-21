"""Actual engine/pipeline construction, database work and required cleanup under interruption."""
import asyncio
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.integration.test_legacy_action_engine_lifetime import hold_engine_input

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_runtime(runtime_type, root, state, monkeypatch, stage, stop):
    original_init, original_close = runtime_type.__init__, runtime_type.close

    def construct(owner, *args, **kwargs):
        if stage == "construction" and stop == "worker_failure":
            hold_engine_input(state, root, failure=True)
        original_init(owner, *args, **kwargs)
        state.owners.append(owner)
        if stage == "construction":
            hold_engine_input(state, root, failure=False)

    async def close(owner):
        if owner._closed:
            return await original_close(owner)
        try:
            if stage == "close":
                await asyncio.to_thread(hold_engine_input, state, root, failure=stop == "worker_failure")
        finally:
            await original_close(owner)

    monkeypatch.setattr(runtime_type, "__init__", construct)
    monkeypatch.setattr(runtime_type, "close", close)


async def exercise_owner(runtime_type, root, state, stage, stop, record_property):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            async with runtime_type.open(root / "workspace", db_path=str(root / "runtime.db"), config_root=root) as owner:
                state.body_entered = True
                await owner.initialize()
                if stage == "body":
                    await run_owned_thread(lambda: hold_engine_input(state, root, failure=stop == "worker_failure"),
                                           label="runtime-context-body-file")

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    pytest.fail(f"Runtime returned before {stage}: {await task}")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
        async with aiosqlite.connect(root / "responsive.sqlite3") as connection:
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
        assert all(not owner._closed for owner in state.owners)
        state.release.set()
        expected = OSError if stop == "worker_failure" else TimeoutError if stop == "timeout" else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(task, 5)
        assert all(owner._closed for owner in state.owners)
        assert all(owner._pipeline._closed for owner in state.owners if isinstance(owner, OrchestrationEngine))
        if stage == "construction":
            assert not state.body_entered
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
        for owner in state.owners:
            await owner.close()
    assert not timer.is_alive() and all(stream.closed for stream in state.files)


@pytest.mark.parametrize("runtime_type", [OrchestrationEngine, ExecutionPipeline], ids=["engine", "pipeline"])
@pytest.mark.parametrize("stage", ["construction", "body", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_runtime_factory_owns_all_admitted_work(tmp_path, monkeypatch, record_property, runtime_type, stage, stop):
    monkeypatch.chdir(tmp_path)
    await asyncio.to_thread((tmp_path / "engine-input.txt").write_text, "owned", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], body_entered=False)
    observe_runtime(runtime_type, tmp_path, state, monkeypatch, stage, stop)
    await exercise_owner(runtime_type, tmp_path, state, stage, stop, record_property)
