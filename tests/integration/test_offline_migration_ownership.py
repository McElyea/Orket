"""Integration: offline adoption and SQLite backup retain native attempts and roots."""
import asyncio
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage import sqlite_backup as backup
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.application.services.outward_authority_migration_service import OutwardAuthorityMigrationService
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.outward_authorization import FixedInputs
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.integration.test_marshaller_attempt_ownership import hold_native
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.integration.test_outward_authority_migration import legacy_queued

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_offline_adoption_captures_database_and_retains_check(tmp_path, monkeypatch, stop, failure, record_property):
    first, other = await roots(tmp_path)
    db, run, _ = await legacy_queued(first)
    other_db, _, other_service = await legacy_queued(other)
    monkeypatch.chdir(first)
    service = OutwardAuthorityMigrationService(Path(db.name), runtime_inputs=FixedInputs())
    inspection = await service.inspect(run.run_id)
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    other_before = await OutwardLedgerSnapshotStore(other_db).read(run.run_id)
    hold = hold_native(monkeypatch, Path, "is_file", lambda path: path.name == db.name, failure)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await service.migrate(run.run_id, expected_run_digest=inspection["expected_run_digest"],
                actor_ref="operator", owners_stopped=True)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        service.db_path, service.unit = other_db, other_service.unit
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        after = await OutwardLedgerSnapshotStore(db).read(run.run_id)
        assert await OutwardLedgerSnapshotStore(other_db).read(run.run_id) == other_before
        if stop == "none" and not failure:
            assert result["authority_state"] == "shared" and len(after.events) == len(before.events) + 1
        else:
            assert after == before
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


def observe_backup_native(monkeypatch, source, targets, phase, failure):
    hold, connections = NativeHold(), []
    connect, execute = aiosqlite.connect, aiosqlite.Connection._execute
    count = 0

    def connection(database, *args, **kwargs):
        result = connect(database, *args, **kwargs)
        if str(database) in {source.as_uri() + "?mode=ro", *(str(path) for path in targets),
                             *(path.as_uri() + "?mode=ro" for path in targets)}:
            connections.append(result)
        return result

    async def observed(conn, fn, *args, **kwargs):
        nonlocal count
        name = getattr(fn, "__name__", "")
        if conn in connections and name == "backup":
            count += 1
        selected = conn in connections and ((phase == "first-backup" and name == "backup" and count == 1) or
            (phase == "second-backup" and name == "backup" and count == 2) or
            (phase == "close" and name == "close")) and not hold.entered.is_set()
        if not selected:
            return await execute(conn, fn, *args, **kwargs)

        def held():
            hold.wait()
            try:
                result = fn(*args, **kwargs)
                if failure:
                    raise OSError("controlled native SQLite failure")
                return result
            finally:
                hold.finished.set()

        return await execute(conn, held)

    monkeypatch.setattr(aiosqlite, "connect", connection)
    monkeypatch.setattr(aiosqlite.Connection, "_execute", observed)
    return hold, connections


async def check_database(path):
    async with aiosqlite.connect(path) as connection:
        return await (await connection.execute("SELECT value FROM native_proof")).fetchall()


@pytest.mark.parametrize("phase", ["first-backup", "second-backup", "close", "digest"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_sqlite_prepare_owns_wal_backup_and_close(tmp_path, monkeypatch, phase, stop, failure, record_property):
    first, other = await roots(tmp_path)
    source, saved, destination = first / "source.sqlite", first / "backup.sqlite", first / "destination.sqlite"
    async with aiosqlite.connect(source) as keeper:
        await keeper.execute("PRAGMA journal_mode=WAL")
        await keeper.execute("CREATE TABLE native_proof (value TEXT)")
        await keeper.execute("INSERT INTO native_proof VALUES ('committed WAL value')")
        await keeper.commit()
        if phase == "digest":
            hold, connections = hold_stream(monkeypatch, saved, "read", failure=failure), []
        else:
            hold, connections = observe_backup_native(monkeypatch, source, [saved, destination], phase, failure)
        deadline = asyncio.timeout(None)

        async def dispatch():
            async with asyncio.timeout(5), deadline:
                return await backup.prepare_sqlite_migration_copy(source=source, backup=saved,
                    destination=destination, writers_stopped=True)

        task = asyncio.create_task(dispatch())
        try:
            result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
            assert_outcome(result, stop, failure)
            for connection in connections:
                with pytest.raises(ValueError, match="no active connection"):
                    await connection.execute("SELECT 1")
            assert await check_database(source) == [("committed WAL value",)]
            assert await check_database(saved) == [("committed WAL value",)]
            if phase in {"second-backup", "digest"} or (stop == "none" and not failure):
                assert await check_database(destination) == [("committed WAL value",)]
            else:
                assert await asyncio.to_thread(destination.read_bytes) == b""
            assert not await file_exists(other / saved.name)
            assert all(stream.closed for stream in getattr(hold, "streams", []))
        finally:
            hold.release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_sqlite_prepare_captures_all_relative_paths_before_resolution(tmp_path, monkeypatch, record_property):
    first, other = await roots(tmp_path)
    source = first / "source.sqlite"
    async with aiosqlite.connect(source) as connection:
        await connection.execute("CREATE TABLE native_proof (value TEXT)")
        await connection.execute("INSERT INTO native_proof VALUES ('original source')")
        await connection.commit()
    monkeypatch.chdir(first)
    hold = hold_native(monkeypatch, Path, "resolve", lambda path, *args, **kwargs: path.name == source.name, False)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await backup.prepare_sqlite_migration_copy(source=Path(source.name), backup=Path("backup.sqlite"),
                destination=Path("destination.sqlite"), writers_stopped=True)

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        assert result.source == source and result.backup == first / "backup.sqlite"
        assert await check_database(result.destination) == [("original source",)]
        assert not await file_exists(other / "destination.sqlite")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
