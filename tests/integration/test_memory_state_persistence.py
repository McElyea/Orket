"""Layer: integration. Historical SQLite schemas, rollback and competing publication."""
import asyncio
from datetime import UTC, datetime

import aiosqlite
import pytest

from orket.adapters.storage import sqlite_connection
from orket.services.memory_store import MemoryStore
from orket.services.scoped_memory_store import ScopedMemoryStore
from tests.helpers.memory_state_probe import MemorySQLProbe, labeled, rows
from tests.integration.test_memory_state_clock import Clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_legacy_project_migration_preserves_rows_defaults_and_fts_retrieval(tmp_path):
    path = tmp_path / "memory.db"
    async with sqlite_connection.connect_sqlite_wal(path) as connection:
        await connection.execute("CREATE TABLE project_memory (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "content TEXT NOT NULL, metadata_json TEXT NOT NULL, keywords TEXT NOT NULL, "
            "created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
        await connection.execute("INSERT INTO project_memory VALUES (1, 'legacy note', '{}', 'legacy note', '2001-01-01 00:00:00')")
        await connection.commit()
    store = MemoryStore(path, runtime_inputs=Clock(datetime(2030, 1, 1, tzinfo=UTC)))
    await store.remember("current note")
    assert await rows(path, "SELECT content, created_at FROM project_memory ORDER BY id") == [
        ("legacy note", "2001-01-01 00:00:00"), ("current note", "2030-01-01 00:00:00")]
    columns = {row[1]: row for row in await rows(path, "PRAGMA table_info(project_memory)")}
    assert columns["created_at"][4] == "CURRENT_TIMESTAMP" and "content_hash" in columns
    assert {row["content"] for row in await store.search("note")} == {"legacy note", "current note"}
    assert [row["content"] for row in await store.search("")] == ["current note", "legacy note"]


@pytest.mark.parametrize("scope", ["session", "episodic", "profile"])
async def test_legacy_scoped_defaults_and_created_time_survive_explicit_update(tmp_path, scope):
    path = tmp_path / "memory.db"
    episodic = scope == "episodic"
    table = "extension_episodic_memory" if episodic else "extension_memory"
    session = "__profile__" if scope == "profile" else "session"
    identity = "session_id TEXT NOT NULL, memory_key TEXT NOT NULL"
    if not episodic:
        identity = "scope TEXT NOT NULL CHECK(scope IN ('session_memory', 'profile_memory')), " + identity
    keys = "session_id, memory_key" if episodic else "scope, session_id, memory_key"
    async with sqlite_connection.connect_sqlite_wal(path) as connection:
        await connection.execute(f"CREATE TABLE {table} ({identity}, memory_value TEXT NOT NULL, "
            "metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            f"updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY({keys}))")
        values = (session, "companion_setting.theme", "old", "{}", "2001-01-01 00:00:00", "2002-01-01 00:00:00")
        if not episodic:
            values = (scope + "_memory", *values)
        await connection.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values)})", values)
        await connection.commit()
    schema = await rows(path, "SELECT sql FROM sqlite_master WHERE name=?", (table,))
    store = ScopedMemoryStore(path, runtime_inputs=Clock(datetime(2030, 1, 1, tzinfo=UTC)))
    arguments = dict(key="companion_setting.theme", value="updated")
    if scope != "profile":
        arguments["session_id"] = session
    result = await getattr(store, "write_" + scope)(**arguments)
    assert result.created_at == "2001-01-01 00:00:00" and result.updated_at == "2030-01-01 00:00:00"
    assert await rows(path, "SELECT sql FROM sqlite_master WHERE name=?", (table,)) == schema
    assert await rows(path, f"SELECT memory_value, created_at, updated_at FROM {table}") == [
        ("updated", "2001-01-01 00:00:00", "2030-01-01 00:00:00")]


async def test_project_native_abort_rolls_back_base_and_fts_changes_then_recovers(tmp_path, monkeypatch):
    path = tmp_path / "memory.db"
    store = MemoryStore(path)
    await store._ensure_initialized()
    async with sqlite_connection.connect_sqlite_wal(path) as connection:
        await connection.execute("CREATE TRIGGER reject_memory AFTER INSERT ON project_memory BEGIN "
            "INSERT INTO project_memory_fts(rowid,content,keywords) VALUES(new.id,new.content,new.keywords); "
            "SELECT RAISE(ABORT, 'native memory refusal'); END")
        await connection.commit()
    probe = MemorySQLProbe(monkeypatch, [])
    with pytest.raises(aiosqlite.IntegrityError, match="native memory refusal"):
        await store.remember("recovered note")
    assert await rows(path, "SELECT COUNT(*) FROM project_memory") == [(0,)]
    assert await rows(path, "SELECT COUNT(*) FROM project_memory_fts") == [(0,)]
    async with sqlite_connection.connect_sqlite_wal(path) as connection:
        await connection.execute("DROP TRIGGER reject_memory")
        await connection.commit()
    await store.remember("recovered note")
    assert [row["content"] for row in await store.search("recovered")] == ["recovered note"]
    await probe.assert_closed()


@pytest.mark.parametrize("kind", ["project", "scoped"])
async def test_independent_cold_stores_publish_without_losing_rows(tmp_path, monkeypatch, kind):
    path = tmp_path / "memory.db"
    probe = MemorySQLProbe(monkeypatch, [])
    if kind == "project":
        await asyncio.gather(*(MemoryStore(path).remember(f"note {i}") for i in range(12)))
        assert await rows(path, "SELECT COUNT(*) FROM project_memory") == [(12,)]
        assert await rows(path, "SELECT COUNT(*) FROM project_memory_fts") == [(12,)]
    else:
        results = await asyncio.gather(*(ScopedMemoryStore(path).write_session(
            session_id="session", key=f"topic{i}", value=f"note{i}") for i in range(12)))
        assert {result.value for result in results} == {f"note{i}" for i in range(12)}
        assert await rows(path, "SELECT COUNT(*) FROM extension_memory") == [(12,)]
    await probe.assert_closed()


@pytest.mark.parametrize("scope", ["session", "episodic", "profile"])
async def test_returned_record_belongs_to_its_writer_under_competing_overwrite(tmp_path, monkeypatch, scope):
    path = tmp_path / "memory.db"
    stores = [ScopedMemoryStore(path), ScopedMemoryStore(path)]
    await stores[0].ensure_initialized()
    entered, release = asyncio.Event(), asyncio.Event()
    original = stores[0]._repository.publish

    async def hold_actual_publication(*args, **kwargs):
        record = await original(*args, **kwargs)
        entered.set()
        await release.wait()
        return record

    monkeypatch.setattr(stores[0]._repository, "publish", hold_actual_publication)
    probe = MemorySQLProbe(monkeypatch, ["second"])
    arguments = dict(key="companion_setting.theme")
    if scope != "profile":
        arguments["session_id"] = "session"
    first = asyncio.create_task(getattr(stores[0], "write_" + scope)(**arguments, value="first"))
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        second = asyncio.create_task(labeled("second", getattr(stores[1], "write_" + scope)(**arguments, value="second")))
        await probe.wait("second")
        assert not first.done() and not second.done()
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([second] if second else [])), 10)
    assert [record.value for record in results] == ["first", "second"]
    table = "extension_episodic_memory" if scope == "episodic" else "extension_memory"
    assert await rows(path, f"SELECT memory_value FROM {table}") == [("second",)]
    await probe.assert_closed()
