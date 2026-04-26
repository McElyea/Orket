from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.runtime.truthful_memory_policy import evaluate_memory_write_policy

from .profile_write_policy import ProfileWritePolicy, ProfileWritePolicyError

MemoryScope = Literal["session_memory", "profile_memory", "episodic_memory"]


@dataclass(frozen=True)
class ScopedMemoryRecord:
    scope: MemoryScope
    key: str
    value: str
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class MemoryControls:
    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True
    episodic_memory_enabled: bool = False

    def effective_session_enabled(self) -> bool:
        return bool(self.session_memory_enabled)

    def effective_profile_enabled(self) -> bool:
        return bool(self.profile_memory_enabled)

    def effective_episodic_enabled(self) -> bool:
        return bool(self.episodic_memory_enabled)


class ScopedMemoryStore:
    def __init__(self, db_path: Path, *, profile_write_policy: ProfileWritePolicy | None = None) -> None:
        self._db_path = db_path.resolve()
        self._profile_write_policy = profile_write_policy or ProfileWritePolicy()

    async def ensure_initialized(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with connect_sqlite_wal(self._db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_memory (
                    scope TEXT NOT NULL CHECK(scope IN ('session_memory', 'profile_memory')),
                    session_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(scope, session_id, memory_key)
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_memory_scope_session_updated
                ON extension_memory(scope, session_id, updated_at DESC, memory_key ASC)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_memory_profile_key
                ON extension_memory(scope, memory_key ASC, created_at ASC)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS extension_episodic_memory (
                    session_id TEXT NOT NULL,
                    memory_key TEXT NOT NULL,
                    memory_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(session_id, memory_key)
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_extension_episodic_memory_session_updated
                ON extension_episodic_memory(session_id, updated_at DESC, memory_key ASC)
                """
            )
            await conn.commit()

    @staticmethod
    def normalize_session_id(scope: MemoryScope, session_id: str) -> str:
        if scope == "profile_memory":
            return "__profile__"
        normalized = str(session_id or "").strip()
        return normalized or "__default_session__"

    async def write_session(
        self,
        *,
        session_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScopedMemoryRecord:
        decision = evaluate_memory_write_policy(
            scope="session_memory",
            key=key,
            value=value,
            metadata=metadata or {},
        )
        return await self._write_record(
            scope="session_memory",
            session_id=self.normalize_session_id("session_memory", session_id),
            key=key,
            value=value,
            metadata=decision.metadata,
        )

    async def write_episodic(
        self,
        *,
        session_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScopedMemoryRecord:
        decision = evaluate_memory_write_policy(
            scope="episodic_memory",
            key=key,
            value=value,
            metadata=metadata or {},
        )
        return await self._write_episodic_record(
            session_id=self.normalize_session_id("episodic_memory", session_id),
            key=key,
            value=value,
            metadata=decision.metadata,
        )

    async def write_profile(
        self,
        *,
        key: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> ScopedMemoryRecord:
        metadata_payload = dict(metadata or {})
        self._profile_write_policy.validate(key=key, metadata=metadata_payload)
        existing = await self.read_profile(key=key)
        decision = evaluate_memory_write_policy(
            scope="profile_memory",
            key=key,
            value=value,
            metadata=metadata_payload,
            existing_value=(existing.value if existing is not None else ""),
            existing_metadata=(existing.metadata if existing is not None else {}),
        )
        if not decision.allow_write:
            raise ProfileWritePolicyError(
                code=str(decision.error_code or "E_PROFILE_MEMORY_WRITE_REJECTED"),
                message=decision.error_message or f"Profile memory key '{key}' was rejected by memory policy.",
            )
        return await self._write_record(
            scope="profile_memory",
            session_id=self.normalize_session_id("profile_memory", ""),
            key=key,
            value=value,
            metadata=decision.metadata,
        )

    async def clear_session(self, *, session_id: str) -> int:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("session_memory", session_id)
        async with connect_sqlite_wal(self._db_path) as conn:
            cursor = await conn.execute(
                """
                DELETE FROM extension_memory
                WHERE scope = 'session_memory' AND session_id = ?
                """,
                (resolved_session,),
            )
            await conn.commit()
            return int(cursor.rowcount or 0)

    async def clear_episodic(self, *, session_id: str) -> int:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("episodic_memory", session_id)
        async with connect_sqlite_wal(self._db_path) as conn:
            cursor = await conn.execute(
                """
                DELETE FROM extension_episodic_memory
                WHERE session_id = ?
                """,
                (resolved_session,),
            )
            await conn.commit()
            return int(cursor.rowcount or 0)

    async def query_session(self, *, session_id: str, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("session_memory", session_id)
        bounded_limit = _bounded_limit(limit)
        normalized_query = str(query or "").strip()
        args: tuple[Any, ...]
        if normalized_query:
            like_query = f"%{normalized_query}%"
            sql = """
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'session_memory' AND session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, like_query, like_query, bounded_limit)
        else:
            sql = """
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'session_memory' AND session_id = ?
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, bounded_limit)
        return await self._query_records(sql=sql, args=args)

    async def query_episodic(self, *, session_id: str, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("episodic_memory", session_id)
        bounded_limit = _bounded_limit(limit)
        normalized_query = str(query or "").strip()
        args: tuple[Any, ...]
        if normalized_query:
            like_query = f"%{normalized_query}%"
            sql = """
                SELECT 'episodic_memory', session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_episodic_memory
                WHERE session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, like_query, like_query, bounded_limit)
        else:
            sql = """
                SELECT 'episodic_memory', session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_episodic_memory
                WHERE session_id = ?
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, bounded_limit)
        return await self._query_records(sql=sql, args=args)

    async def read_profile(self, *, key: str) -> ScopedMemoryRecord | None:
        await self.ensure_initialized()
        rows = await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ? AND memory_key = ?
                LIMIT 1
                """,
            args=(self.normalize_session_id("profile_memory", ""), str(key or "").strip()),
        )
        return rows[0] if rows else None

    async def list_profile(self, *, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        return await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ?
                ORDER BY memory_key ASC, created_at ASC
                LIMIT ?
                """,
            args=(self.normalize_session_id("profile_memory", ""), _bounded_limit(limit)),
        )

    async def query_profile(self, *, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        normalized_query = str(query or "").strip()
        like_query = f"%{normalized_query}%"
        return await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """,
            args=(self.normalize_session_id("profile_memory", ""), like_query, like_query, _bounded_limit(limit)),
        )

    async def _write_episodic_record(
        self,
        *,
        session_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any],
    ) -> ScopedMemoryRecord:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self._db_path) as conn:
            await conn.execute(
                """
                INSERT INTO extension_episodic_memory
                (
                    session_id, memory_key, memory_value, metadata_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id, memory_key)
                DO UPDATE SET
                    memory_value = excluded.memory_value,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    session_id,
                    str(key or "").strip(),
                    str(value or ""),
                    json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                ),
            )
            await conn.commit()
        record = await self._read_episodic_record(session_id=session_id, key=key)
        if record is None:
            raise RuntimeError("E_SCOPED_MEMORY_EPISODIC_WRITE_READBACK_FAILED")
        return record

    async def _write_record(
        self,
        *,
        scope: MemoryScope,
        session_id: str,
        key: str,
        value: str,
        metadata: dict[str, Any],
    ) -> ScopedMemoryRecord:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self._db_path) as conn:
            await conn.execute(
                """
                INSERT INTO extension_memory
                (
                    scope, session_id, memory_key, memory_value, metadata_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, session_id, memory_key)
                DO UPDATE SET
                    memory_value = excluded.memory_value,
                    metadata_json = excluded.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    scope,
                    session_id,
                    str(key or "").strip(),
                    str(value or ""),
                    json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                ),
            )
            await conn.commit()
        record = await self._read_record(scope=scope, session_id=session_id, key=key)
        if record is None:
            raise RuntimeError("E_SCOPED_MEMORY_WRITE_READBACK_FAILED")
        return record

    async def _read_episodic_record(self, *, session_id: str, key: str) -> ScopedMemoryRecord | None:
        rows = await self._query_records(
            sql="""
                SELECT 'episodic_memory', session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_episodic_memory
                WHERE session_id = ? AND memory_key = ?
                LIMIT 1
                """,
            args=(session_id, str(key or "").strip()),
        )
        return rows[0] if rows else None

    async def _read_record(self, *, scope: MemoryScope, session_id: str, key: str) -> ScopedMemoryRecord | None:
        rows = await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = ? AND session_id = ? AND memory_key = ?
                LIMIT 1
                """,
            args=(scope, session_id, str(key or "").strip()),
        )
        return rows[0] if rows else None

    async def _query_records(self, *, sql: str, args: tuple[Any, ...]) -> list[ScopedMemoryRecord]:
        async with connect_sqlite_wal(self._db_path) as conn:
            cursor = await conn.execute(sql, args)
            rows = await cursor.fetchall()
        return [_row_to_record(tuple(row)) for row in rows]


def _bounded_limit(limit: int) -> int:
    return max(1, min(200, int(limit)))


def _row_to_record(row: tuple[Any, ...]) -> ScopedMemoryRecord:
    scope_raw, session_id, key, value, metadata_json, created_at, updated_at = row
    scope = str(scope_raw or "").strip()
    metadata = _parse_metadata(metadata_json)
    return ScopedMemoryRecord(
        scope=scope,  # type: ignore[arg-type]
        key=str(key or ""),
        value=str(value or ""),
        session_id=str(session_id or "") if scope in {"session_memory", "episodic_memory"} else "",
        metadata=metadata,
        created_at=str(created_at or ""),
        updated_at=str(updated_at or ""),
    )


def _parse_metadata(payload: Any) -> dict[str, Any]:
    raw = str(payload or "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return {str(key): value for key, value in decoded.items()}
    return {}
