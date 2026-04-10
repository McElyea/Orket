from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite

ResultT = TypeVar("ResultT")


class AsyncFlowRepository:
    """Async SQLite repository for persisted flow definitions."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._write_lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flows (
                flow_id TEXT PRIMARY KEY,
                revision_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    async def _execute(
        self,
        operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
        *,
        commit: bool = False,
        row_factory: bool = False,
    ) -> ResultT:
        async def _run() -> ResultT:
            async with aiosqlite.connect(self.db_path) as conn:
                if row_factory:
                    conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                result = await operation(conn)
                if commit:
                    await conn.commit()
                return result

        if commit:
            async with self._write_lock:
                return await _run()
        return await _run()

    async def list_flows(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        async def _op(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
            cursor = await conn.execute(
                """
                SELECT flow_id, revision_id, name, description, payload_json, created_at, updated_at
                FROM flows
                ORDER BY datetime(updated_at) DESC, flow_id DESC
                LIMIT ? OFFSET ?
                """,
                (max(1, int(limit)), max(0, int(offset))),
            )
            rows = await cursor.fetchall()
            return [self._deserialize_row(dict(row)) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def get_flow(self, flow_id: str) -> dict[str, Any] | None:
        async def _op(conn: aiosqlite.Connection) -> dict[str, Any] | None:
            cursor = await conn.execute(
                """
                SELECT flow_id, revision_id, name, description, payload_json, created_at, updated_at
                FROM flows
                WHERE flow_id = ?
                """,
                (flow_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._deserialize_row(dict(row))

        return await self._execute(_op, row_factory=True)

    async def save_flow(
        self,
        *,
        flow_id: str,
        revision_id: str,
        name: str,
        description: str,
        payload: dict[str, Any],
        created_at: str,
        updated_at: str,
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=True, sort_keys=True)

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT OR REPLACE INTO flows (
                    flow_id, revision_id, name, description, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (flow_id, revision_id, name, description, payload_json, created_at, updated_at),
            )

        await self._execute(_op, commit=True)

    def _deserialize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        payload_raw = row.get("payload_json")
        payload = {}
        if payload_raw:
            payload = json.loads(str(payload_raw))
        row["payload"] = payload if isinstance(payload, dict) else {}
        row.pop("payload_json", None)
        return row
