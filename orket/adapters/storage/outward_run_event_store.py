from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
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
    )
]


class OutwardRunEventStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            async with connect_sqlite_wal(self.db_path) as conn:
                await SQLiteMigrationRunner(namespace="outward_run_events").apply(conn, _MIGRATIONS)
                await conn.commit()
            self._initialized = True

    async def append(self, event: LedgerEvent) -> LedgerEvent:
        self._validate_event(event)
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO run_events (
                    event_id, event_type, run_id, turn, agent_id, at, payload_json, event_hash, chain_hash
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.run_id,
                    event.turn,
                    event.agent_id,
                    event.at,
                    _payload_json(event.payload),
                    event.event_hash,
                    event.chain_hash,
                ),
            )
            await conn.commit()
        return event

    async def get(self, event_id: str) -> LedgerEvent | None:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM run_events WHERE event_id = ?", (event_id,))
            row = await cursor.fetchone()
        return _row_to_event(row) if row is not None else None

    async def update_hashes(self, *, event_id: str, event_hash: str, chain_hash: str) -> None:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE run_events
                SET event_hash = ?, chain_hash = ?
                WHERE event_id = ?
                """,
                (event_hash, chain_hash, event_id),
            )
            await conn.commit()

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
        return [_row_to_event(row) for row in rows]

    @staticmethod
    def _validate_event(event: LedgerEvent) -> None:
        if not event.event_id.strip():
            raise ValueError("event_id is required")
        if not event.event_type.strip():
            raise ValueError("event_type is required")
        if not event.run_id.strip():
            raise ValueError("run_id is required")
        if not event.at.strip():
            raise ValueError("at is required")


def _payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _row_to_event(row: aiosqlite.Row) -> LedgerEvent:
    return LedgerEvent(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        run_id=str(row["run_id"]),
        turn=row["turn"],
        agent_id=row["agent_id"],
        at=str(row["at"]),
        payload=json.loads(str(row["payload_json"])),
        event_hash=row["event_hash"],
        chain_hash=row["chain_hash"],
    )


__all__ = ["OutwardRunEventStore"]
