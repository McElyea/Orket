"""Integration: required bug-fix events with real SQLite and physical log effects."""
import asyncio
import json
import threading
from copy import deepcopy

import aiosqlite
import pytest

from orket.application.services import bug_fix_phase_manager as phases
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from tests.integration.test_bug_fix_phase_effects import manager

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def records(path):
    def read():
        return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
    return await asyncio.to_thread(read)


async def persisted(path):
    async with (asyncio.timeout(0.5), aiosqlite.connect(path) as connection,
                connection.execute("SELECT rock_id FROM bug_fix_phases") as cursor):
        return await cursor.fetchall()


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", ["none", "before", "after"])
async def test_required_phase_event_retains_inputs_and_native_outcome(tmp_path, monkeypatch, stop, failure):
    owner = manager(tmp_path)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    native, publish = phases.log_event, owner._publish
    state = {}
    native_failure = OSError("controlled required phase event failure")

    async def observe(phase, event=None, payload=None):
        state["payload"], state["expected"] = payload, deepcopy(payload)
        return await publish(phase, event, payload)

    def held(event, payload, workspace):
        state["worker"] = threading.get_ident()
        entered.set()
        try:
            assert release.wait(5)
            if failure == "before":
                raise native_failure
            native(event, payload, workspace)
            if failure == "after":
                raise native_failure
        finally:
            finished.set()

    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await owner.start_phase("rock")

    monkeypatch.setattr(owner, "_publish", observe)
    monkeypatch.setattr(phases, "log_event", held)
    root = owner.workspace
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path, timezone_name="MST"))):
        task = asyncio.create_task(dispatch())
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            assert state["worker"] != threading.get_ident() and await persisted(owner.db.db_path) == [("rock",)]
            state["payload"]["rock_id"] = "late mutation"
            owner.workspace = tmp_path / "late"
            monkeypatch.chdir(tmp_path)
            monkeypatch.setenv("ORKET_TIMEZONE", "UTC")
            if stop == "timeout":
                deadline.reschedule(asyncio.get_running_loop().time() + 0.1)
            if stop == "cancel":
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
            await asyncio.sleep(0.15 if stop == "timeout" else 0)
            assert not task.done()
            release.set()
            result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert finished.is_set()
            assert_outcome(result, failure, stop, native_failure)
            rows = await records(root / "orket.log")
            if failure == "before":
                assert not rows
            else:
                row, = rows
                assert row["data"]["rock_id"] == state["expected"]["rock_id"]
                assert row["timestamp"].endswith("-07:00")
            assert not await records(tmp_path / "late/orket.log")
            assert await persisted(owner.db.db_path) == [("rock",)]
            assert owner.active_phases["rock"].rock_id == "rock"
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_phase_event_selects_workspace_before_persistence_wait(tmp_path, monkeypatch):
    owner = manager(tmp_path)
    native = owner.db.save_bug_fix_phase
    entered, release = asyncio.Event(), asyncio.Event()

    async def held(phase):
        await native(phase)
        entered.set()
        await release.wait()

    monkeypatch.setattr(owner.db, "save_bug_fix_phase", held)
    workspace = owner.workspace
    with bind_logging(await prepare_logging(LoggingInputs(tmp_path))):
        task = asyncio.create_task(owner.start_phase("rock"))
        try:
            await asyncio.wait_for(entered.wait(), 3)
            assert await persisted(owner.db.db_path) == [("rock",)]
            owner.workspace = tmp_path / "late"
            release.set()
            assert (await asyncio.wait_for(task, 5)).rock_id == "rock"
            row, = await records(workspace / "orket.log")
            assert row["event"] == "bug_fix_phase_started"
            assert not await records(tmp_path / "late/orket.log")
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


def assert_outcome(result, failure, stop, native_failure):
    if failure != "none":
        assert result is native_failure
    elif stop != "none":
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
    else:
        assert result.rock_id == "rock"
