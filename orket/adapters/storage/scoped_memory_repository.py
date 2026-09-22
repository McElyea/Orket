"""SQLite effects for application-owned scoped memory operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal

side_effecting = True


class ScopedMemoryRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def initialize(self):
        await run_owned_thread(
            partial(self.db_path.parent.mkdir, parents=True, exist_ok=True), label="scoped-memory directory"
        )
        async with connect_sqlite_wal(self.db_path) as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS extension_memory (
                    scope TEXT NOT NULL CHECK(scope IN ('session_memory', 'profile_memory')),
                    session_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(scope, session_id, memory_key)
                )
            """)
            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_extension_memory_scope_session_updated
                ON extension_memory(scope, session_id, updated_at DESC, memory_key ASC)
            """)
            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_extension_memory_profile_key
                ON extension_memory(scope, memory_key ASC, created_at ASC)
            """)
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS extension_episodic_memory (
                    session_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, memory_key)
                )
            """)
            await connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_extension_episodic_memory_session_updated
                ON extension_episodic_memory(session_id, updated_at DESC, memory_key ASC)
            """)
            await connection.commit()

    @asynccontextmanager
    async def transaction(self):
        async with connect_sqlite_wal(self.db_path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            yield connection
            await connection.commit()

    async def read(self, connection, *, scope, session_id, key):
        table, columns, identity = _identity(scope, session_id, key)
        scope_column = "'episodic_memory'" if scope == "episodic_memory" else "scope"
        sql = (
            f"SELECT {scope_column}, session_id, memory_key, memory_value, metadata_json, created_at, updated_at "
            f"FROM {table} WHERE " + " AND ".join(f"{column} = ?" for column in columns)
        )
        async with connection.execute(sql, identity) as cursor:
            row = await cursor.fetchone()
        return tuple(row) if row is not None else None

    async def publish(self, connection, *, scope, session_id, key, value, metadata_json, timestamp):
        table, columns, identity = _identity(scope, session_id, key)
        inserted = (*columns, "memory_value", "metadata_json", "created_at", "updated_at")
        sql = (
            f"INSERT INTO {table} ({', '.join(inserted)}) VALUES ({', '.join('?' for _ in inserted)}) "
            f"ON CONFLICT ({', '.join(columns)}) DO UPDATE SET memory_value=excluded.memory_value, "
            "metadata_json=excluded.metadata_json, updated_at=excluded.updated_at"
        )
        await connection.execute(sql, (*identity, value, metadata_json, timestamp, timestamp))
        return await self.read(connection, scope=scope, session_id=session_id, key=key)

    async def query(self, *, sql, args):
        async with connect_sqlite_wal(self.db_path) as connection, connection.execute(sql, args) as cursor:
            return [tuple(row) for row in await cursor.fetchall()]

    async def clear(self, *, scope, session_id):
        table, columns, identity = _identity(scope, session_id, "")
        sql = f"DELETE FROM {table} WHERE " + " AND ".join(f"{column} = ?" for column in columns[:-1])
        async with self.transaction() as connection, connection.execute(sql, identity[:-1]) as cursor:
            return int(cursor.rowcount or 0)


def _identity(scope, session_id, key):
    # SQL identifiers come only from this closed mapping, never caller strings.
    if scope == "episodic_memory":
        return "extension_episodic_memory", ("session_id", "memory_key"), (session_id, key)
    if scope in {"session_memory", "profile_memory"}:
        return "extension_memory", ("scope", "session_id", "memory_key"), (scope, session_id, key)
    raise ValueError("E_SCOPED_MEMORY_SCOPE_INVALID")
