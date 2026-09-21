"""Actual legacy engine/file lifetime with an explicitly controlled action-result port."""
import asyncio
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.extensions.contracts import RunAction, RunPlan
from orket.extensions.workload_executor_support import execute_plan_actions
from orket.orchestration.engine import OrchestrationEngine
from tests.helpers.runtime_result import published_result

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_engine_input(state, root, *, failure):
    try:
        with (root / "engine-input.txt").open("rb") as stream:
            state.files.append(stream)
            assert stream.read() == b"owned"
            state.entered.set()
            assert state.release.wait(5), "Legacy engine worker release deadline"
            if failure:
                (root / "absent-engine-input.txt").read_bytes()
    finally:
        state.finished.set()


def install_engine_probe(root, monkeypatch, state, stage, stop):
    def construct(*args, **kwargs):
        if stage == "construction" and stop == "worker_failure":
            hold_engine_input(state, root, failure=True)
        owner = OrchestrationEngine(*args, **kwargs)
        state.owners.append(owner)
        original_close = owner.close
        state.cleanup.append(original_close)

        async def close():
            if owner._closed:
                return await original_close()
            try:
                if stage == "close":
                    await asyncio.to_thread(hold_engine_input, state, root, failure=stop == "worker_failure")
            finally:
                await original_close()

        async def action(card_id, **options):
            # Synthetic published result is only the action port; not runtime completion proof.
            state.actions.append((card_id, options))
            await owner.initialize()
            if stage == "action":
                await run_owned_thread(lambda: hold_engine_input(state, root, failure=stop == "worker_failure"),
                                       label="legacy-action-fixture-input")
            return published_result(session_id=card_id)

        monkeypatch.setattr(owner, "close", close)
        monkeypatch.setattr(owner, "run_card", action)
        if stage == "construction":
            hold_engine_input(state, root, failure=False)
        return owner

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", construct)


async def interrupt_action(root, state, stage, stop, record_property):
    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await execute_plan_actions(run_plan=RunPlan("owned", "1", (RunAction("run_card", "fixture"),)),
                                              workspace=root / "workspace", department="core", interaction_context=None)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    pytest.fail(f"Action returned before {stage} admission: {await task}")
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
        assert all(owner._closed and owner._pipeline._closed for owner in state.owners)
        if stage == "construction":
            assert state.actions == []
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
        for close in state.cleanup:
            await close()
    assert not timer.is_alive() and all(stream.closed for stream in state.files)


@pytest.mark.parametrize("stage", ["construction", "action", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_legacy_action_owns_engine_through_interruption(tmp_path, monkeypatch, record_property, stage, stop):
    monkeypatch.chdir(tmp_path)
    await asyncio.to_thread((tmp_path / "engine-input.txt").write_text, "owned", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], cleanup=[], actions=[])
    install_engine_probe(tmp_path, monkeypatch, state, stage, stop)
    await interrupt_action(tmp_path, state, stage, stop, record_property)
