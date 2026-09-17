from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.sqlite_connection import sqlite_connection_scope


class AsyncPendingGateRepository:
    """
    Persistent ledger for pending gate/approval/review requests.
    """

    side_effecting = True

    def __init__(self, db_path: str | Path, *, connection: aiosqlite.Connection | None = None) -> None:
        self.db_path = str(db_path)
        self._connection = connection
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_gate_requests (
                request_id TEXT PRIMARY KEY,
                session_id TEXT,
                issue_id TEXT,
                seat_name TEXT,
                gate_mode TEXT,
                request_type TEXT,
                reason TEXT,
                payload_json TEXT,
                status TEXT,
                resolution_json TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                resolved_at DATETIME
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_gate_requests_session ON pending_gate_requests(session_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_gate_requests_status ON pending_gate_requests(status)"
        )

    async def create_request(
        self,
        *,
        session_id: str,
        issue_id: str,
        seat_name: str,
        gate_mode: str,
        request_type: str,
        reason: str,
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
        request_id: str | None = None,
    ) -> str:
        request_id = str(request_id or uuid.uuid4())[:64]
        now = str(created_at or datetime.now(UTC).isoformat())
        async with self._lock, sqlite_connection_scope(self.db_path, self._connection) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                """
                    INSERT OR IGNORE INTO pending_gate_requests
                    (request_id, session_id, issue_id, seat_name, gate_mode, request_type, reason,
                     payload_json, status, resolution_json, created_at, updated_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    request_id,
                    session_id,
                    issue_id,
                    seat_name,
                    gate_mode,
                    request_type,
                    reason,
                    json.dumps(payload or {}),
                    "pending",
                    None,
                    now,
                    now,
                    None,
                ),
            )
        return request_id

    async def resolve_request(
        self,
        *,
        request_id: str,
        status: str,
        resolution: dict[str, Any] | None = None,
        resolved_at: str | None = None,
        expected_status: str | None = None,
    ) -> bool:
        now = str(resolved_at or datetime.now(UTC).isoformat())
        async with self._lock, sqlite_connection_scope(self.db_path, self._connection) as conn:
            await self._ensure_initialized(conn)
            cursor = await conn.execute(
                """
                    UPDATE pending_gate_requests
                    SET status = ?, resolution_json = ?, updated_at = ?, resolved_at = ?
                    WHERE request_id = ? AND (? IS NULL OR status = ?)
                    """,
                (status, json.dumps(resolution or {}), now, now, request_id, expected_status, expected_status),
            )
            return cursor.rowcount == 1

    async def list_requests(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self._lock, sqlite_connection_scope(self.db_path, self._connection) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_initialized(conn)

            where_parts: list[str] = []
            params: list[Any] = []
            if session_id:
                where_parts.append("session_id = ?")
                params.append(session_id)
            if status:
                where_parts.append("status = ?")
                params.append(status)

            where_clause = ""
            if where_parts:
                where_clause = "WHERE " + " AND ".join(where_parts)

            params.append(limit)
            cursor = await conn.execute(
                f"""
                    SELECT * FROM pending_gate_requests
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                tuple(params),
            )
            rows = await cursor.fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                for key in ("payload_json", "resolution_json"):
                    if item.get(key):
                        try:
                            item[key] = json.loads(item[key])
                        except json.JSONDecodeError:
                            item[key] = {}
                    else:
                        item[key] = {}
                results.append(item)
            return results
