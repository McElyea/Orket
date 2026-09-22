"""Layer: integration. Actual native effects, retained ownership and independent responsiveness."""
from pathlib import Path

import pytest

from orket.services.memory_store import MemoryStore
from orket.services.scoped_memory_store import ScopedMemoryStore
from tests.helpers.memory_lifetime_probe import NativeMemoryHold
from tests.helpers.memory_state_probe import rows

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("scope", ["project", "session", "episodic", "profile"])
@pytest.mark.parametrize("mode", ["cancel", "repeated", "timeout"])
async def test_memory_write_drains_native_transaction_before_interruption(tmp_path, monkeypatch, scope, mode, record_property):
    path = tmp_path / "memory.db"
    store = MemoryStore(path) if scope == "project" else ScopedMemoryStore(path)
    if scope == "project":
        await store._ensure_initialized()
        operation = store.remember("durably owned")
        table, column = "project_memory", "content"
    else:
        await store.ensure_initialized()
        arguments = dict(key="companion_setting.theme", value="durably owned")
        if scope != "profile":
            arguments["session_id"] = "session"
        operation = getattr(store, "write_" + scope)(**arguments)
        table = "extension_episodic_memory" if scope == "episodic" else "extension_memory"
        column = "memory_value"
    hold = NativeMemoryHold(monkeypatch)
    hold.sqlite(monkeypatch, "INSERT INTO " + table.upper() + " ")
    record_property("independent_sqlite_seconds", await hold.interrupt(operation, mode, tmp_path / "independent.db"))
    assert await rows(path, f"SELECT {column} FROM {table}") == [("durably owned",)]
    if scope == "project":
        assert await rows(path, "SELECT content FROM project_memory_fts") == [("durably owned",)]


@pytest.mark.parametrize("kind", ["project", "scoped"])
@pytest.mark.parametrize("mode", ["cancel", "repeated", "timeout"])
async def test_memory_initialization_retains_native_directory_worker(tmp_path, monkeypatch, kind, mode, record_property):
    path = tmp_path / "new-directory" / "memory.db"
    store = MemoryStore(path) if kind == "project" else ScopedMemoryStore(path)
    hold = NativeMemoryHold(monkeypatch)
    original = Path.mkdir

    def mkdir(directory, *args, **kwargs):
        result = original(directory, *args, **kwargs)
        if directory == path.parent and not hold.entered.is_set():
            hold.hold()
        return result

    monkeypatch.setattr(Path, "mkdir", mkdir)
    operation = store.remember("initialized") if kind == "project" else store.write_session(
        session_id="session", key="topic", value="initialized")
    record_property("independent_sqlite_seconds", await hold.interrupt(operation, mode, tmp_path / "independent.db"))
    table, column = ("project_memory", "content") if kind == "project" else ("extension_memory", "memory_value")
    assert await rows(path, f"SELECT {column} FROM {table}") == [("initialized",)]


@pytest.mark.parametrize("kind", ["project", "session", "episodic", "profile", "clear_session", "clear_episodic"])
async def test_memory_read_and_clear_keep_native_connection_until_repeated_cancel_drains(tmp_path, monkeypatch, kind, record_property):
    path = tmp_path / "memory.db"
    if kind == "project":
        store = MemoryStore(path)
        await store.remember("read me")
        operation, prefix = store.search(""), "SELECT * FROM PROJECT_MEMORY"
    else:
        store = ScopedMemoryStore(path)
        await store.write_profile(key="companion_setting.theme", value="read me")
        await store.write_session(session_id="session", key="topic", value="read me")
        await store.write_episodic(session_id="session", key="topic", value="read me")
        if kind == "profile":
            operation = store.read_profile(key="companion_setting.theme")
        elif kind.startswith("clear_"):
            operation = getattr(store, kind)(session_id="session")
        else:
            operation = getattr(store, "query_" + kind)(session_id="session", query="", limit=10)
        prefix = "DELETE FROM" if kind.startswith("clear_") else "SELECT"
    hold = NativeMemoryHold(monkeypatch)
    hold.sqlite(monkeypatch, prefix)
    record_property("independent_sqlite_seconds", await hold.interrupt(operation, "repeated", tmp_path / "independent.db"))
    if kind == "clear_session":
        assert await rows(path, "SELECT COUNT(*) FROM extension_memory WHERE scope='session_memory'") == [(0,)]
    elif kind == "clear_episodic":
        assert await rows(path, "SELECT COUNT(*) FROM extension_episodic_memory") == [(0,)]
