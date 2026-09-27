"""Real filesystem/SQLite cleanup observations; Docker responses are fixtures."""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.verification import AGENT_OUTPUT_DIR
from tests.helpers.logging_async_opening import sqlite_observation
from tests.integration.test_sandbox_runtime_recovery_service import FakeRecoveryRunner, _record, _service

pytestmark = pytest.mark.integration


async def _prepare(tmp_path):
    runner = FakeRecoveryRunner(compose_project="orket-sandbox-sb-1", sandbox_id="sb-1", run_id="run-1")
    repo, recovery = _service(tmp_path, runner)
    compose = tmp_path / AGENT_OUTPUT_DIR / "deployment" / "docker-compose.sandbox.yml"
    await asyncio.to_thread(compose.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(compose.touch)
    await repo.save_record(_record(
        state=SandboxState.TERMINAL, cleanup_state=CleanupState.SCHEDULED,
        record_version=4, requires_reconciliation=False, terminal_reason=TerminalReason.SUCCESS,
        terminal_at="2026-03-11T00:00:00+00:00", cleanup_due_at="2026-03-11T00:01:00+00:00",
        workspace_path=str(tmp_path),
    ))
    return repo, recovery, runner, compose


async def _invoke(recovery, execute):
    if execute:
        return await recovery.sweep_due_cleanups(max_records=1)
    return await recovery.preview_due_cleanups(max_records=1)


@pytest.mark.parametrize("execute", [False, True], ids=["preview", "execute"])
async def test_cleanup_receipt_uses_authorization_file_observation(tmp_path, monkeypatch, execute):
    repo, recovery, runner, compose = await _prepare(tmp_path)
    exists = Path.exists
    observed = []

    def remove_after_observation(path):
        present = exists(path)
        if path == compose:
            observed.append(present)
            path.unlink(missing_ok=True)
        return present

    monkeypatch.setattr(Path, "exists", remove_after_observation)
    results = await _invoke(recovery, execute)
    events = await repo.list_events("sb-1")
    decisions = [event.payload for event in events if event.event_type == "sandbox.cleanup_decision_evaluated"]
    assert len(results) == len(decisions) == 1
    assert decisions[0]["cleanup_strategy"] == "compose"
    assert decisions[0]["compose_path_available"] is True
    assert observed == [True]
    assert not exists(compose)
    assert any("down" in call for call in runner.async_calls) is execute


@pytest.mark.parametrize("execute", [False, True], ids=["preview", "execute"])
async def test_cleanup_metadata_stays_native(tmp_path, monkeypatch, execute):
    _, recovery, _, compose = await _prepare(tmp_path)
    exists, loop_thread = Path.exists, threading.get_ident()
    observed_threads = []

    def observe_thread(path):
        if path == compose:
            observed_threads.append(threading.get_ident())
        return exists(path)

    monkeypatch.setattr(Path, "exists", observe_thread)
    assert len(await _invoke(recovery, execute)) == 1
    assert observed_threads and loop_thread not in observed_threads


@pytest.mark.parametrize("execute", [False, True], ids=["preview", "execute"])
async def test_cleanup_retains_held_metadata_through_repeated_cancel(
    tmp_path, monkeypatch, record_property, execute,
):
    repo, recovery, _, compose = await _prepare(tmp_path)
    exists = Path.exists
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def hold_exists(path):
        if path != compose:
            return exists(path)
        entered.set()
        try:
            assert release.wait(5), "fixture metadata hold expired"
            return exists(path)
        finally:
            finished.set()

    monkeypatch.setattr(Path, "exists", hold_exists)
    operation = asyncio.create_task(_invoke(recovery, execute))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        observation = await sqlite_observation(tmp_path / "independent.sqlite3", time.perf_counter())
        record_property("responsive_sqlite_seconds", observation["elapsed"])
        assert observation["row"] == (42,) and 0 < observation["elapsed"] < 0.5
        operation.cancel("first interruption")
        await asyncio.sleep(0)
        operation.cancel("second interruption")
        await asyncio.sleep(0)
        assert not operation.done(), "cleanup caller escaped its admitted native observation"
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        assert await asyncio.to_thread(finished.wait, 5)
    assert operation.cancelled()
    with pytest.raises(asyncio.CancelledError, match="first interruption"):
        operation.result()
    events = await repo.list_events("sb-1")
    assert not any(event.event_type == "sandbox.cleanup_decision_evaluated" for event in events)
