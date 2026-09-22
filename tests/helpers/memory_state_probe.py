"""Native SQLite admission observations for memory integration tests."""
from __future__ import annotations

import asyncio
import contextvars
import threading
from contextlib import asynccontextmanager

from orket.adapters.storage import sqlite_connection
from tests.integration.test_sqlite_wal_admission import _assert_closed, _observe_connections

ATTEMPT = contextvars.ContextVar("memory_state_attempt", default="")


class MemorySQLProbe:
    def __init__(self, monkeypatch, labels, *, prefixes=("BEGIN IMMEDIATE", "INSERT INTO")):
        self.events = {label: threading.Event() for label in labels}
        self.statements = []
        self.connections, _ = _observe_connections(monkeypatch)
        original = sqlite_connection.ensure_wal_mode

        async def observe(connection):
            result = await original(connection)
            label = ATTEMPT.get()
            if label in self.events:
                def trace(statement):
                    normalized = " ".join(statement.upper().split())
                    if normalized.startswith(prefixes):
                        self.statements.append((label, normalized.split("VALUES")[0]))
                        self.events[label].set()
                await connection.set_trace_callback(trace)
            return result

        monkeypatch.setattr(sqlite_connection, "ensure_wal_mode", observe)

    async def wait(self, label):
        # Release the independent native writer before the unchanged 5s busy limit.
        assert await asyncio.wait_for(asyncio.to_thread(self.events[label].wait, 2), 3), self.statements

    async def assert_closed(self):
        await _assert_closed(self.connections)


async def labeled(label, operation):
    token = ATTEMPT.set(label)
    try:
        return await operation
    finally:
        ATTEMPT.reset(token)


@asynccontextmanager
async def writer_lock(path):
    async with sqlite_connection.connect_sqlite_wal(path) as connection:
        await connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        finally:
            await connection.rollback()


async def rows(path, sql, args=()):
    async with sqlite_connection.connect_sqlite_wal(path) as connection, connection.execute(sql, args) as cursor:
        return await cursor.fetchall()
