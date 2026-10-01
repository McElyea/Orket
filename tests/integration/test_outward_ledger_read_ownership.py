"""Integration: retained ledger observations own native work without acquiring write authority."""
from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.core.domain.outward_ledger_integrity import OutwardLedgerIntegrityError
from tests.helpers.governed_read_ownership import NativeReadProbe, interrupt_held_read
from tests.helpers.outward_ledger import logical_contents, seed_ledger
from tests.helpers.runtime_verification_hold import wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _invoke(route, service):
    if route == "snapshot":
        return await service.snapshot_store.read("bt2")
    if route == "export":
        return await service.export("bt2")
    return await service.verify_run("bt2")


def _assert_count(route, result, count):
    if route == "snapshot":
        assert result.independent_count == result.anchor.event_count == len(result.events) == count
    else:
        assert result["canonical"]["event_count"] == result["retained"]["anchor"]["event_count"] == count
        assert result["verification"]["result"] == "valid"
        assert result["retained"]["authenticity"] == "not_established"


@pytest.mark.parametrize("route,boundary", [
    ("snapshot", "resolve"), ("snapshot", "connect"), ("snapshot", "query"), ("snapshot", "close"),
    ("export", "resolve"), ("export", "close"), ("verify", "resolve"), ("verify", "close"),
])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_ledger_observation_retains_native_work_and_close(
    tmp_path, monkeypatch, record_property, route, boundary, mode,
):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    before = await asyncio.to_thread(logical_contents, path)
    probe = NativeReadProbe(monkeypatch, path, boundary)
    task = asyncio.create_task(_invoke(route, service))
    waiter = None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        await probe.assert_settled()
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("surface", ["read", "read_in_transaction"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_borrowed_transaction_retains_query_but_leaves_connection_with_caller(
    tmp_path, monkeypatch, record_property, surface, mode,
):
    path = tmp_path / "ledger.sqlite3"
    await seed_ledger(path, 3)
    before = await asyncio.to_thread(logical_contents, path)
    probe = NativeReadProbe(monkeypatch, path, "observe")
    task = waiter = None
    try:
        connection = await aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA query_only=ON")
        await connection.execute("BEGIN")
        reader = OutwardLedgerSnapshotStore(Path(tmp_path.drive + "unused-database"),
                                           page_size=2, connection=connection)
        probe.boundary = "query"
        operation = reader.read("bt2") if surface == "read" else reader.read_in_transaction(connection, "bt2")
        task = asyncio.create_task(operation)
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        assert probe.finished.is_set() and not probe.expired and not probe.native[0].closed
        assert connection.in_transaction
        assert tuple(await (await connection.execute("SELECT 42")).fetchone()) == (42,)
        await connection.rollback()
        await connection.close()
        await probe.assert_settled()
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup(task, waiter)


async def test_export_retains_selected_store_bindings_across_preflight(tmp_path, monkeypatch):
    path, other = tmp_path / "ledger.sqlite3", tmp_path / "other.sqlite3"
    service = await seed_ledger(path, 3)
    await seed_ledger(other, 1)
    before = [await asyncio.to_thread(logical_contents, target) for target in (path, other)]
    probe = NativeReadProbe(monkeypatch, path, "resolve")
    task = asyncio.create_task(service.export("bt2"))
    try:
        await wait_entered(probe)
        service.run_store.db_path = service.event_store.db_path = service.snapshot_store.db_path = other
        probe.release.set()
        _assert_count("export", await task, 3)
        await probe.assert_settled()
        assert [await asyncio.to_thread(logical_contents, target) for target in (path, other)] == before
    finally:
        await probe.cleanup(task)


async def test_snapshot_retains_page_size_before_query_wait(tmp_path, monkeypatch):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    reader = OutwardLedgerSnapshotStore(path, page_size=2)
    before = await asyncio.to_thread(logical_contents, path)
    probe = NativeReadProbe(monkeypatch, path, "query")
    task = asyncio.create_task(reader.read("bt2"))
    try:
        await wait_entered(probe)
        reader.page_size = 0
        probe.release.set()
        _assert_count("snapshot", await task, 3)
        await probe.assert_settled()
        assert await asyncio.to_thread(logical_contents, path) == before
        assert (await service.verify_run("bt2"))["retained_integrity"] == "valid"
    finally:
        await probe.cleanup(task)


@pytest.mark.parametrize("route", ["snapshot", "export"])
async def test_relative_ledger_path_binds_before_native_wait(tmp_path, monkeypatch, route):
    selected, changed = tmp_path / "selected", tmp_path / "changed"
    path, other = selected / "ledger.sqlite3", changed / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    await seed_ledger(other, 1)
    before = [await asyncio.to_thread(logical_contents, target) for target in (path, other)]
    service.run_store.db_path = service.event_store.db_path = service.snapshot_store.db_path = Path(path.name)
    monkeypatch.chdir(selected)
    probe = NativeReadProbe(monkeypatch, path, "resolve")
    task = asyncio.create_task(_invoke(route, service))
    try:
        await wait_entered(probe)
        monkeypatch.chdir(changed)
        probe.release.set()
        _assert_count(route, await task, 3)
        await probe.assert_settled()
        assert [await asyncio.to_thread(logical_contents, target) for target in (path, other)] == before
    finally:
        monkeypatch.chdir(selected)
        await probe.cleanup(task)


@pytest.mark.parametrize("route", ["snapshot", "export"])
async def test_drive_relative_ledger_path_refuses_before_native_work(tmp_path, monkeypatch, route):
    if not tmp_path.drive:
        pytest.skip("Windows drive-relative path policy")
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 1)
    before = await asyncio.to_thread(logical_contents, path)
    relative = Path(tmp_path.drive + path.name)
    service.run_store.db_path = service.event_store.db_path = service.snapshot_store.db_path = relative
    probe = NativeReadProbe(monkeypatch, path, "observe")
    try:
        with pytest.raises(ValueError, match="E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
            await _invoke(route, service)
        assert not probe.path_calls and not probe.native and not probe.connections
        await probe.assert_settled(held=False)
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup()


@pytest.mark.parametrize("initially_valid", [True, False])
async def test_verification_retains_anchor_mapping_without_changing_validation(tmp_path, monkeypatch, initially_valid):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    anchor = (await service.export("bt2"))["retained"]["anchor"]
    if not initially_valid:
        anchor["unexpected"] = ["invalid mapping field"]
    before = await asyncio.to_thread(logical_contents, path)
    probe = NativeReadProbe(monkeypatch, path, "query")
    task = asyncio.create_task(service.verify_run("bt2", external_anchor=anchor))
    try:
        await wait_entered(probe)
        if initially_valid:
            anchor["chain_hash"] = "0" * 64
        else:
            anchor.pop("unexpected")
        probe.release.set()
        report = await task
        assert report["result"] == ("valid" if initially_valid else "invalid")
        assert report["external_anchor"] == ("matched_prefix" if initially_valid else "invalid")
        assert report["errors"] == ([] if initially_valid else ["E_OUTWARD_LEDGER_ANCHOR_SCHEMA"])
        assert report["retained_integrity"] == report["snapshot_completeness"] == "valid"
        assert report["authenticity"] == "not_established"
        await probe.assert_settled()
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup(task)


async def test_anchor_pair_sequence_is_not_newly_admitted(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 1)
    anchor = (await service.export("bt2"))["retained"]["anchor"]
    before = await asyncio.to_thread(logical_contents, path)
    report = await service.verify_run("bt2", external_anchor=list(anchor.items()))
    assert report["result"] == report["external_anchor"] == "invalid"
    assert report["errors"] == ["E_OUTWARD_LEDGER_ANCHOR_SCHEMA"]
    assert report["retained_integrity"] == "valid"
    assert await asyncio.to_thread(logical_contents, path) == before


@pytest.mark.parametrize("route", ["snapshot", "export", "verify"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_uncaught_preflight_failure_retains_identity_after_interruption(
    tmp_path, monkeypatch, record_property, route, mode,
):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    before = await asyncio.to_thread(logical_contents, path)
    failure = OSError("controlled ledger preflight failure")
    probe = NativeReadProbe(monkeypatch, path, "resolve", failure=failure)
    task = asyncio.create_task(_invoke(route, service))
    waiter = None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        await probe.assert_settled()
        assert not probe.native and not probe.connections
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("route", ["snapshot", "verify"])
async def test_query_failure_preserves_storage_cause_and_public_invalid_report(
    tmp_path, monkeypatch, record_property, route,
):
    path = tmp_path / "ledger.sqlite3"
    service = await seed_ledger(path, 3)
    before = await asyncio.to_thread(logical_contents, path)
    failure = sqlite3.OperationalError("controlled query acknowledgement failure")
    probe = NativeReadProbe(monkeypatch, path, "query", failure=failure)
    task = asyncio.create_task(_invoke(route, service))
    try:
        await interrupt_held_read(task, probe, "cancel", tmp_path / "independent.sqlite3", record_property)
        probe.release.set()
        if route == "snapshot":
            with pytest.raises(OutwardLedgerIntegrityError) as observed:
                await task
            assert observed.value.category == "storage" and observed.value.__cause__ is failure
        else:
            report = await task
            assert report["result"] == "invalid" and report["external_anchor"] == "not_checked"
            assert report["retained_integrity"] == report["snapshot_completeness"] == "not_verified"
            assert report["checked_event_count"] == 0 and report["event_count"] is None
            assert report["errors"] == [f"E_OUTWARD_LEDGER_STORAGE_READ: {failure}"]
        await probe.assert_settled()
        assert await asyncio.to_thread(logical_contents, path) == before
    finally:
        await probe.cleanup(task)
