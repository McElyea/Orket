"""Integration: captured store paths and explicitly borrowed SQLite schema authority."""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.outward_store_ownership import (
    STORES,
    TABLES,
    NativeStoreProbe,
    borrow,
    state,
    stores_and_service,
    submission,
)
from tests.helpers.runtime_verification_hold import wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("initialized", [False, True])
@pytest.mark.parametrize("family,operation", [
    ("runs", "create"), ("runs", "update"), ("runs", "get"), ("runs", "get_active_by_namespace"),
    ("approvals", "save"), ("approvals", "get"), ("approvals", "count_for_run"), ("approvals", "update_decision"),
    ("events", "append"), ("events", "get"),
])
async def test_borrowed_connection_never_initializes_unrelated_store_path(tmp_path, family, operation, initialized):
    path, unrelated = tmp_path / "selected.sqlite3", tmp_path / "unrelated" / "other.sqlite3"
    if initialized:
        await STORES[family](path).ensure_initialized()
    store = STORES[family](unrelated)
    async with aiosqlite.connect(path) as connection:
        await connection.execute("BEGIN IMMEDIATE")
        if initialized:
            result = await borrow(store, family, operation, connection)
            if operation in {"get", "get_active_by_namespace"}:
                assert result is None
            elif operation == "count_for_run":
                assert result == 0
            elif operation == "update_decision":
                assert result is False
            else:
                assert result.run_id == "owned-run"
        else:
            with pytest.raises(aiosqlite.OperationalError, match="no such table"):
                await borrow(store, family, operation, connection)
        assert connection.in_transaction, "borrowed transaction was committed or rolled back"
        assert tuple(await (await connection.execute("SELECT 1")).fetchone()) == (1,)
        assert not await asyncio.to_thread(unrelated.parent.exists)
        await connection.rollback()
    if initialized:
        assert (await state(path))[TABLES[family]] == 0
    else:
        assert await state(path) == {}


async def test_unit_captures_store_references_paths_and_keeps_public_method_seam(tmp_path, monkeypatch):
    path, other = tmp_path / "selected.sqlite3", tmp_path / "other.sqlite3"
    stores, unit, service = stores_and_service(path)
    replacement, _replacement_unit, _replacement_service = stores_and_service(other)
    original_get, seen = stores["runs"].get, []

    async def get(run_id, *, connection=None):
        seen.append(connection)
        return await original_get(run_id, connection=connection)

    monkeypatch.setattr(stores["runs"], "get", get)
    probe = NativeStoreProbe(monkeypatch, path, "resolve")
    task = asyncio.create_task(service.submit(submission()))
    try:
        await wait_entered(probe)
        for store in stores.values():
            store.db_path = other
        unit._runs, unit._approvals, unit._events = (replacement[name] for name in ("runs", "approvals", "events"))
        probe.release.set()
        assert (await task).run_id == "owned-run"
        await probe.assert_settled()
        assert len(seen) == 1 and seen[0] in probe.connections
        assert not await asyncio.to_thread(other.exists)
        counts = await state(path)
        assert counts["outward_runs"] == counts["run_events"] == counts["control_plane_runs"] == 1
    finally:
        await probe.cleanup(task)


async def test_unit_relative_paths_bind_before_native_resolution(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(second.mkdir)
    path = first / "selected.sqlite3"
    stores, _unit, service = stores_and_service(path)
    for store in stores.values():
        store.db_path = Path("selected.sqlite3")
    monkeypatch.chdir(first)
    probe = NativeStoreProbe(monkeypatch, path, "resolve")
    task = asyncio.create_task(service.submit(submission()))
    try:
        await wait_entered(probe)
        monkeypatch.chdir(second)
        probe.release.set()
        assert (await task).run_id == "owned-run"
        await probe.assert_settled()
        assert (await state(path))["run_events"] == 1
        assert not await asyncio.to_thread((second / path.name).exists)
    finally:
        monkeypatch.chdir(first)
        await probe.cleanup(task)


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_path_resolution_failure_precedes_interruption_without_initialization(
    tmp_path, monkeypatch, record_property, mode,
):
    path = tmp_path / "selected.sqlite3"
    _stores, _unit, service = stores_and_service(path)
    failure = OSError("native path resolution acknowledgement failed")
    probe = NativeStoreProbe(monkeypatch, path, "resolve", failure=failure)
    task, waiter = asyncio.create_task(service.submit(submission())), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        await probe.assert_settled()
        assert probe.connections == [] and not await asyncio.to_thread(path.exists)
    finally:
        await probe.cleanup(task, waiter)


async def test_mismatched_databases_refuse_before_any_initializer_effect(tmp_path):
    path, other = tmp_path / "selected.sqlite3", tmp_path / "other.sqlite3"
    stores, _unit, service = stores_and_service(path)
    stores["events"].db_path = other
    with pytest.raises(RuntimeError, match="E_OUTWARD_TRANSACTION_DATABASE_MISMATCH"):
        await service.submit(submission())
    assert not await asyncio.to_thread(path.exists) and not await asyncio.to_thread(other.exists)


async def test_event_initializer_preserves_missing_parent_refusal(tmp_path):
    path = tmp_path / "absent" / "selected.sqlite3"
    with pytest.raises(aiosqlite.OperationalError, match="unable to open database"):
        await STORES["events"](path).ensure_initialized()
    assert not await asyncio.to_thread(path.parent.exists)


async def test_populated_legacy_approval_refuses_without_rewriting_history(tmp_path):
    path = tmp_path / "selected.sqlite3"
    async with aiosqlite.connect(path) as connection:
        await connection.execute("CREATE TABLE outward_approval_proposals (proposal_id TEXT)")
        await connection.execute("INSERT INTO outward_approval_proposals VALUES ('legacy')")
        await connection.commit()
    with pytest.raises(RuntimeError, match="E_OUTWARD_OFFLINE_APPROVAL_MIGRATION_REQUIRED"):
        await STORES["approvals"](path).ensure_initialized()
    async with aiosqlite.connect(path) as connection:
        assert await (await connection.execute("SELECT * FROM outward_approval_proposals")).fetchall() == [("legacy",)]
        assert await (await connection.execute(
            "SELECT name FROM sqlite_master WHERE name='outward_approval_proposals_v2'",
        )).fetchall() == []
