"""Integration: public wake fences/replay retain actual native reads and cleanup."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityStaleError
from tests.helpers.governed_read_ownership import (
    NativeReadProbe,
    interrupt_held_read,
    invoke_read,
    prepare_reads,
)
from tests.helpers.runtime_verification_hold import sqlite_response, wait_entered
from tests.integration.test_async_governed_agent_wake_repository import _request
from tests.integration.test_governed_agent_replay_evidence import _dump
from tests.integration.test_governed_agent_supervisor import _Clock, _CompletingDispatcher, _supervisor, _TaskOwner

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _prepare_other_database(path):
    path.parent.mkdir()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")


@pytest.mark.parametrize("family", ["wake", "replay"])
@pytest.mark.parametrize("boundary", ["resolve", "exists", "connect", "query", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_public_read_retains_native_attempt_and_connection_close(
    tmp_path, monkeypatch, record_property, family, boundary, mode,
):
    path = tmp_path / "read.sqlite3"
    authority = await prepare_reads(path)
    before = await asyncio.to_thread(_dump, path)
    probe = NativeReadProbe(monkeypatch, path, boundary)
    task = asyncio.create_task(invoke_read(family, path, authority))
    waiter = None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        await probe.assert_settled()
        assert await asyncio.to_thread(_dump, path) == before
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("family", ["wake", "replay"])
async def test_public_read_binds_relative_database_before_native_resolution(
    tmp_path, monkeypatch, family,
):
    selected, changed = tmp_path / "selected", tmp_path / "changed"
    await asyncio.to_thread(selected.mkdir)
    path = selected / "read.sqlite3"
    authority = await prepare_reads(path)
    await asyncio.to_thread(_prepare_other_database, changed / path.name)
    before = await asyncio.to_thread(_dump, path)
    other_before = await asyncio.to_thread(_dump, changed / path.name)
    monkeypatch.chdir(selected)
    probe = NativeReadProbe(monkeypatch, path, "resolve")
    task = asyncio.create_task(invoke_read(family, Path(path.name), authority))
    try:
        await wait_entered(probe)
        monkeypatch.chdir(changed)
        probe.release.set()
        result = await task
        if family == "wake":
            assert result == "active"
        else:
            assert result["ok"] and result["status"] == "matched"
            assert result["expected_count"] == result["compared_count"] == result["matched_count"] == 1
            assert result["external_effects_verified"] is result["full_execution_verified"] is False
        await probe.assert_settled()
        assert await asyncio.to_thread(_dump, path) == before
        assert await asyncio.to_thread(_dump, changed / path.name) == other_before
    finally:
        monkeypatch.chdir(selected)
        await probe.cleanup(task)


@pytest.mark.parametrize("family", ["wake", "replay"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_preflight_failure_keeps_original_identity_after_caller_interruption(
    tmp_path, monkeypatch, record_property, family, mode,
):
    path = tmp_path / "read.sqlite3"
    authority = await prepare_reads(path)
    before = await asyncio.to_thread(_dump, path)
    failure = OSError("controlled read preflight failure")
    probe = NativeReadProbe(monkeypatch, path, "resolve", failure=failure)
    task = asyncio.create_task(invoke_read(family, path, authority))
    waiter = None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        await probe.assert_settled()
        assert not probe.native and not probe.connections
        assert await asyncio.to_thread(_dump, path) == before
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("family", ["wake", "replay"])
async def test_drive_relative_database_refuses_before_native_read(tmp_path, monkeypatch, family):
    if not tmp_path.drive:
        pytest.skip("drive-relative path semantics require Windows")
    selected = tmp_path / "read.sqlite3"
    authority = await prepare_reads(selected)
    before = await asyncio.to_thread(_dump, selected)
    probe = NativeReadProbe(monkeypatch, selected, "observe")
    with pytest.raises(ValueError, match="E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
        await invoke_read(family, Path(tmp_path.drive + "read.sqlite3"), authority)
    assert not probe.path_calls and not probe.native and not probe.connections
    assert await asyncio.to_thread(_dump, selected) == before


@pytest.mark.parametrize("family", ["wake", "replay"])
async def test_missing_database_read_creates_no_path_or_authority(tmp_path, family):
    authority = await prepare_reads(tmp_path / "existing.sqlite3")
    missing = tmp_path / "absent" / "read.sqlite3"
    failure = GovernedAgentAuthorityStaleError if family == "wake" else ValueError
    reason = "E_AGENT_WAKE_CLAIM_STALE" if family == "wake" else "E_AGENT_RUN_NOT_FOUND"
    with pytest.raises(failure, match=reason):
        await invoke_read(family, missing, authority)
    assert not await asyncio.to_thread(missing.parent.exists)


@pytest.mark.parametrize("family", ["wake", "replay"])
async def test_native_connection_refusal_preserves_public_failure_scope(tmp_path, monkeypatch, family):
    path = tmp_path / "read.sqlite3"
    authority = await prepare_reads(path)
    before = await asyncio.to_thread(_dump, path)
    refused = tmp_path / "database-is-a-directory"
    await asyncio.to_thread(refused.mkdir)
    probe = NativeReadProbe(monkeypatch, refused, "observe")
    task = asyncio.create_task(invoke_read(family, refused, authority))
    try:
        if family == "wake":
            with pytest.raises(sqlite3.OperationalError):
                await task
        else:
            result = await task
            assert result["ok"] is False and result["status"] == "insufficient_evidence"
            assert result["expected_count"] is None and result["compared_count"] == 0
            assert result["diagnostics"] == ["evidence_unreadable:OperationalError", "terminal_authority_conflict",
                                             "run_identity_missing_or_mismatched"]
        assert len(probe.connections) == 1 and not probe.native
        await probe.assert_settled(held=False)
        assert await asyncio.to_thread(lambda: list(refused.iterdir())) == []
        assert await asyncio.to_thread(_dump, path) == before
    finally:
        await probe.cleanup(task)


@pytest.mark.parametrize("boundary", ["resolve", "connect"])
async def test_supervisor_shutdown_retains_fence_before_uncertain_release(
    tmp_path, monkeypatch, record_property, boundary,
):
    path = tmp_path / "read.sqlite3"
    repository = AsyncGovernedAgentWakeRepository(path)
    await repository.enqueue(_request())
    dispatcher, owner = _CompletingDispatcher(), _TaskOwner()
    supervisor = _supervisor(repository, dispatcher, _Clock())
    probe = NativeReadProbe(monkeypatch, path, boundary)
    serving = supervisor.start(owner)
    closing = None
    try:
        await wait_entered(probe)
        closing = asyncio.create_task(supervisor.close())
        await asyncio.sleep(0)
        assert serving.cancelling() == 1
        assert await sqlite_response(tmp_path / "independent.sqlite3", record_property) < 0.5
        assert not closing.done() and not serving.done(), "supervisor close abandoned its native fence"
        retained = await repository.get_wake(wake_id="wake-1")
        assert retained.state == "claimed" and retained.last_reason is None
        assert dispatcher.calls == [] and len(owner.tasks) == 1
        probe.release.set()
        await closing
        await probe.assert_settled()
        await asyncio.sleep(0)
        assert not supervisor.running and owner.tasks == set() and dispatcher.calls == []
        retained = await repository.get_wake(wake_id="wake-1")
        assert retained.state == "recovery_required" and retained.uncertainty
        assert retained.last_reason == "supervisor_cancelled" and retained.result_ref is None
    finally:
        probe.release.set()
        if not serving.done():
            serving.cancel()
        await probe.cleanup(serving, closing)
        await supervisor.close()
