"""Layer: integration. Real SQLite contention, bounded admission and connection teardown."""
import asyncio
import sqlite3
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from orket.adapters.storage import sqlite_connection as adapter

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@asynccontextmanager
async def _exclusive_database(path):
    async with aiosqlite.connect(path) as blocker:
        await blocker.execute("CREATE TABLE records (value TEXT NOT NULL)")
        await blocker.commit()
        assert await adapter.current_journal_mode(path) == "delete"
        await blocker.execute("BEGIN EXCLUSIVE")
        try:
            yield blocker
        finally:
            await blocker.rollback()


def _observe_connections(monkeypatch):
    original = aiosqlite.connect
    observed = []
    repeated = asyncio.Event()

    def connect(*args, **kwargs):
        connection = original(*args, **kwargs)
        observed.append(connection)
        if len(observed) > 1:
            repeated.set()
        return connection

    monkeypatch.setattr(adapter.aiosqlite, "connect", connect)
    return observed, repeated


async def _assert_closed(connections):
    for connection in connections:
        # aiosqlite versions either own a thread or subclass Thread themselves.
        thread = getattr(connection, "_thread", connection)
        if thread.ident is not None:
            await asyncio.to_thread(thread.join, 1)
        assert not thread.is_alive()
        with pytest.raises(ValueError, match="no active connection"):
            await connection.execute("SELECT 1")


async def test_wal_admission_releases_busy_connections_before_success(tmp_path, monkeypatch):
    path = tmp_path / "memory.sqlite3"
    observed = []

    async def admit():
        async with adapter.connect_sqlite_wal(path) as connection:
            async with connection.execute("PRAGMA journal_mode") as cursor:
                assert await cursor.fetchone() == ("wal",)
            async with connection.execute("PRAGMA busy_timeout") as cursor:
                assert await cursor.fetchone() == (5000,)
            await connection.execute("INSERT INTO records VALUES ('admitted')")
            await connection.commit()

    async with _exclusive_database(path) as blocker:
        observed, repeated = _observe_connections(monkeypatch)
        task = asyncio.create_task(admit())
        try:
            await asyncio.wait_for(repeated.wait(), 2)
            assert not task.done()
        finally:
            await blocker.rollback()
            await asyncio.wait_for(task, 5)
    assert len(observed) > 1
    await _assert_closed(observed)


async def test_wal_admission_retained_lock_exhausts_budget_without_yield(tmp_path, monkeypatch):
    path = tmp_path / "locked.sqlite3"
    yielded = False
    async with _exclusive_database(path):
        observed, _ = _observe_connections(monkeypatch)
        started = asyncio.get_running_loop().time()
        with pytest.raises(aiosqlite.OperationalError) as error:
            async with asyncio.timeout(7):
                async with adapter.connect_sqlite_wal(path):
                    yielded = True
        assert error.value.sqlite_errorcode & 0xFF == sqlite3.SQLITE_BUSY
        assert asyncio.get_running_loop().time() - started >= 4.5
    assert not yielded
    await _assert_closed(observed)


async def test_wal_admission_cancellation_closes_pending_connections(tmp_path, monkeypatch):
    path = tmp_path / "cancelled.sqlite3"
    yielded = False

    async def admit():
        nonlocal yielded
        async with adapter.connect_sqlite_wal(path):
            yielded = True

    async with _exclusive_database(path):
        observed, repeated = _observe_connections(monkeypatch)
        task = asyncio.create_task(admit())
        try:
            await asyncio.wait_for(repeated.wait(), 2)
        finally:
            task.cancel()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert not yielded and isinstance(outcome, asyncio.CancelledError)
    await _assert_closed(observed)


async def test_busy_caller_statement_is_never_readmitted_or_replayed(tmp_path, monkeypatch):
    path = tmp_path / "body.sqlite3"
    async with adapter.connect_sqlite_wal(path) as setup:
        await setup.execute("CREATE TABLE records (value TEXT NOT NULL)")
        await setup.commit()
    entries = 0
    async with aiosqlite.connect(path) as blocker:
        await blocker.execute("BEGIN IMMEDIATE")
        observed, _ = _observe_connections(monkeypatch)
        try:
            with pytest.raises(aiosqlite.OperationalError) as error:
                async with adapter.connect_sqlite_wal(path) as caller:
                    entries += 1
                    await caller.execute("PRAGMA busy_timeout=0")
                    await caller.execute("INSERT INTO records VALUES ('forbidden')")
            assert error.value.sqlite_errorcode & 0xFF == sqlite3.SQLITE_BUSY
        finally:
            await blocker.rollback()
        async with blocker.execute("SELECT COUNT(*) FROM records") as cursor:
            assert await cursor.fetchone() == (0,)
    assert entries == len(observed) == 1
    await _assert_closed(observed)


async def test_non_wal_memory_database_is_not_admitted():
    with pytest.raises(RuntimeError, match="journal_mode=memory"):
        async with adapter.connect_sqlite_wal(":memory:"):
            pytest.fail("in-memory database was admitted as WAL")


async def test_invalid_database_error_is_not_retried(tmp_path, monkeypatch):
    observed, _ = _observe_connections(monkeypatch)
    with pytest.raises(aiosqlite.OperationalError) as error:
        async with adapter.connect_sqlite_wal(tmp_path / "absent" / "database.sqlite3"):
            pytest.fail("missing parent was admitted")
    assert error.value.sqlite_errorcode == sqlite3.SQLITE_CANTOPEN
    assert len(observed) == 1
    await _assert_closed(observed)
