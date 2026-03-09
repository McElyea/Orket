from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from orket.capabilities.sync_bridge import run_coro_sync
from orket_extension_sdk.memory import (
    MemoryProvider,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryRecord,
    MemoryWriteRequest,
    MemoryWriteResponse,
)


class SQLiteMemoryCapabilityProvider(MemoryProvider):
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path.resolve()

    async def _ensure_initialized(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_memory (
                    scope TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(scope, session_id, memory_key)
                )
                """
            )
            await conn.commit()

    @staticmethod
    def _normalized_session_id(request_scope: str, session_id: str) -> str:
        if request_scope == "profile_memory":
            return "__profile__"
        return str(session_id or "").strip() or "__default_session__"

    async def _write_async(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        await self._ensure_initialized()
        session_id = self._normalized_session_id(request.scope, request.session_id)
        async with aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                INSERT INTO extension_memory (scope, session_id, memory_key, memory_value, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, session_id, memory_key)
                DO UPDATE SET
                    memory_value = excluded.memory_value,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    request.scope,
                    session_id,
                    request.key,
                    request.value,
                    json.dumps(request.metadata, sort_keys=True, separators=(",", ":")),
                ),
            )
            await conn.commit()
        return MemoryWriteResponse(
            ok=True,
            scope=request.scope,
            key=request.key,
            session_id=session_id if request.scope == "session_memory" else "",
        )

    async def _query_async(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        await self._ensure_initialized()
        session_id = self._normalized_session_id(request.scope, request.session_id)
        limit = max(1, min(200, int(request.limit)))
        query = str(request.query or "").strip()
        like_query = f"%{query}%"
        rows: list[tuple[str, str, str, str]] = []
        async with aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute(
                """
                SELECT scope, session_id, memory_key, memory_value
                FROM extension_memory
                WHERE scope = ? AND session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """,
                (request.scope, session_id, like_query, like_query, limit),
            )
            rows = await cursor.fetchall()
        records = [
            MemoryRecord(
                scope=scope,
                session_id=row_session if scope == "session_memory" else "",
                key=key,
                value=value,
                metadata={},
            )
            for scope, row_session, key, value in rows
        ]
        return MemoryQueryResponse(ok=True, records=records)

    def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        return run_coro_sync(self._write_async(request))

    def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        return run_coro_sync(self._query_async(request))
