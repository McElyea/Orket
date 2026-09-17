from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.outward_ledger_append_store import (
    LEDGER_APPEND_MIGRATION,
    OutwardEventAppend,
    read_append_head,
)
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal, sqlite_connection_scope
from orket.adapters.storage.sqlite_migrations import SQLiteMigration, SQLiteMigrationRunner
from orket.core.domain.outward_run_events import LedgerEvent

_MIGRATIONS = [
    SQLiteMigration(
        version=1,
        name="create_outward_run_events",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS run_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                run_id TEXT NOT NULL,
                turn INTEGER,
                agent_id TEXT,
                at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                event_hash TEXT,
                chain_hash TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_run_events_run_order ON run_events (run_id, turn, at, event_id)",
            "CREATE INDEX IF NOT EXISTS idx_run_events_type ON run_events (event_type)",
        ),
    ),
    LEDGER_APPEND_MIGRATION,
]


class OutwardRunEventStore:
    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            async with connect_sqlite_wal(self.db_path) as conn:
                await conn.execute("BEGIN IMMEDIATE")
                await SQLiteMigrationRunner(namespace="outward_run_events").apply(conn, _MIGRATIONS)
                await conn.commit()
            self._initialized = True

    async def append(
        self, event: LedgerEvent, *, connection: aiosqlite.Connection | None = None,
    ) -> LedgerEvent:
        await self.ensure_initialized()
        async with sqlite_connection_scope(self.db_path, connection) as conn:
            if not conn.in_transaction:
                await conn.execute("BEGIN IMMEDIATE")
            writer = OutwardEventAppend(conn, await read_append_head(conn, event.run_id))
            return await writer.append(event)

    @asynccontextmanager
    async def writer(self, run_id: str) -> AsyncIterator[OutwardEventAppend]:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield OutwardEventAppend(conn, await read_append_head(conn, run_id))
                await conn.commit()
            finally:
                if conn.in_transaction:
                    await conn.rollback()

    async def get(
        self, event_id: str, *, connection: aiosqlite.Connection | None = None,
    ) -> LedgerEvent | None:
        await self.ensure_initialized()
        async with sqlite_connection_scope(self.db_path, connection) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM run_events WHERE event_id = ?", (event_id,))
            row = await cursor.fetchone()
        return event_from_row(row) if row is not None else None

    async def list_for_run(
        self,
        run_id: str,
        *,
        from_turn: int | None = None,
        to_turn: int | None = None,
        types: tuple[str, ...] = (),
        agent_id: str | None = None,
        limit: int = 1000,
    ) -> list[LedgerEvent]:
        await self.ensure_initialized()
        conditions = ["run_id = ?"]
        params: list[Any] = [run_id]
        if from_turn is not None:
            conditions.append("turn >= ?")
            params.append(int(from_turn))
        if to_turn is not None:
            conditions.append("turn <= ?")
            params.append(int(to_turn))
        clean_types = tuple(str(item).strip() for item in types if str(item).strip())
        if clean_types:
            conditions.append(f"event_type IN ({','.join('?' for _ in clean_types)})")
            params.extend(clean_types)
        clean_agent_id = str(agent_id or "").strip()
        if clean_agent_id:
            conditions.append("agent_id = ?")
            params.append(clean_agent_id)
        params.append(max(1, min(int(limit), 5000)))
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"""
                SELECT * FROM run_events
                WHERE {' AND '.join(conditions)}
                ORDER BY run_id ASC, turn ASC, at ASC, event_id ASC
                LIMIT ?
                """,
                tuple(params),
            )
            rows = await cursor.fetchall()
        return [event_from_row(row) for row in rows]


def event_from_row(row: aiosqlite.Row) -> LedgerEvent:
    return LedgerEvent(
        event_id=row["event_id"],
        event_type=row["event_type"],
        run_id=row["run_id"],
        turn=row["turn"],
        agent_id=row["agent_id"],
        at=row["at"],
        payload=json.loads(str(row["payload_json"])),
        event_hash=row["event_hash"],
        chain_hash=row["chain_hash"],
    )


__all__ = ["OutwardRunEventStore"]
