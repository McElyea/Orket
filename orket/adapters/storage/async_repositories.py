"""Async repositories for session, snapshot and run persistence."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from orket.core.contracts.repositories import SessionRepository, SnapshotRepository
from orket.core.contracts.result_error_invariants import validate_result_error_invariant

from .sqlite_connection import connect_sqlite_wal, ensure_wal_mode

side_effecting = True


class AsyncSessionRepository(SessionRepository):
    """Session persistence using aiosqlite."""
    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await ensure_wal_mode(conn)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                type TEXT,
                name TEXT,
                department TEXT,
                status TEXT,
                task_input TEXT,
                transcript TEXT,
                start_time DATETIME,
                end_time DATETIME
            )
        """)
        await conn.commit()

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'sessions'")).fetchone():
                return None
            cursor = await conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def start_session(self, session_id: str, data: dict[str, Any]) -> None:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                """
                    INSERT OR IGNORE INTO sessions
                    (id, type, name, department, status, task_input, start_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    session_id,
                    data["type"],
                    data["name"],
                    data["department"],
                    "Started",
                    data["task_input"],
                    datetime.now(UTC).isoformat(),
                ),
            )
            await conn.commit()

    async def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_initialized(conn)
            cursor = await conn.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,))
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def get_session_issues(self, session_id: str) -> list[dict[str, Any]]:
        """Return session issues for the shared runtime backlog route."""
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await self._ensure_initialized(conn)

            table_cursor = await conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'issues' LIMIT 1"
            )
            has_issues_table = await table_cursor.fetchone()
            if not has_issues_table:
                return []

            cursor = await conn.execute(
                "SELECT * FROM issues WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
            issues: list[dict[str, Any]] = []
            for row in rows:
                data = dict(row)
                for source_field, target_field, default in (
                    ("verification_json", "verification", {}),
                    ("metrics_json", "metrics", {}),
                    ("depends_on_json", "depends_on", []),
                ):
                    raw = data.get(source_field)
                    if raw:
                        try:
                            data[target_field] = json.loads(raw)
                        except json.JSONDecodeError:
                            data[target_field] = default
                    else:
                        data[target_field] = default
                issues.append(data)
            return issues

    async def complete_session(
        self, session_id: str, status: str, transcript: list[dict[str, Any]]
    ) -> None:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                "UPDATE sessions SET status = ?, transcript = ?, end_time = ? WHERE id = ?",
                (status, json.dumps(transcript), datetime.now(UTC).isoformat(), session_id),
            )
            await conn.commit()


class AsyncSnapshotRepository(SnapshotRepository):
    """Snapshot persistence using aiosqlite."""
    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        if self._initialized:
            return
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_snapshots (
                session_id TEXT PRIMARY KEY,
                config_json TEXT,
                log_history TEXT,
                captured_at DATETIME
            )
        """)
        await conn.commit()
        self._initialized = True

    async def record(self, session_id: str, config: dict[str, Any], logs: list[dict[str, Any]]) -> None:
        db_path, config_json, log_history = self.db_path, json.dumps(config), json.dumps(logs)
        async with self._lock, connect_sqlite_wal(db_path) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                """
                    INSERT OR REPLACE INTO session_snapshots
                    (session_id, config_json, log_history, captured_at)
                    VALUES (?, ?, ?, ?)
                    """,
                (session_id, config_json, log_history, datetime.now(UTC).isoformat()),
            )
            await conn.commit()

    async def get(self, session_id: str) -> dict[str, Any] | None:
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'session_snapshots'")).fetchone():
                return None
            cursor = await conn.execute("SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None


class AsyncSuccessRepository:
    """One retained success record per run."""
    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        if self._initialized:
            return
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS success_ledger (
                session_id TEXT PRIMARY KEY,
                success_type TEXT, -- e.g. 'PR_MERGED', 'ARTIFACT_GENERATED', 'FIT_VERIFIED'
                artifact_ref TEXT, -- Path, PR URL, or Hash
                human_ack TEXT,    -- Nullable: 'Yes'/'No' from the judge
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
        self._initialized = True

    async def get(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'success_ledger'")).fetchone():
                return None
            row = await (await conn.execute("SELECT * FROM success_ledger WHERE session_id = ?", (session_id,))).fetchone()
            return dict(row) if row else None

    async def record_success(
        self, session_id: str, success_type: str, artifact_ref: str, human_ack: str | None = None
    ) -> None:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                """
                    INSERT OR REPLACE INTO success_ledger
                    (session_id, success_type, artifact_ref, human_ack)
                    VALUES (?, ?, ?, ?)
                    """,
                (session_id, success_type, artifact_ref, human_ack),
            )
            await conn.commit()


class AsyncRunLedgerRepository:
    """Unified run ledger for success, failure, and incomplete outcomes."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        if self._initialized:
            return
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_ledger (
                session_id TEXT PRIMARY KEY,
                run_type TEXT,
                run_name TEXT,
                department TEXT,
                build_id TEXT,
                status TEXT,
                failure_class TEXT,
                failure_reason TEXT,
                summary_json TEXT,
                artifact_json TEXT,
                started_at DATETIME,
                ended_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        await conn.commit()
        self._initialized = True

    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            await self._ensure_initialized(conn)
            await conn.execute(
                """
                    INSERT OR REPLACE INTO run_ledger
                    (session_id, run_type, run_name, department, build_id, status, failure_class, failure_reason,
                     summary_json, artifact_json, started_at, ended_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    session_id,
                    run_type,
                    run_name,
                    department,
                    build_id,
                    "running",
                    None,
                    None,
                    json.dumps(summary or {}),
                    json.dumps(artifacts or {}),
                    now,
                    None,
                    now,
                ),
            )
            await conn.commit()

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: str | None = None,
        failure_reason: str | None = None,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        finalized_at: str | None = None,
    ) -> None:
        resolved_status = validate_result_error_invariant(
            status=status,
            failure_class=failure_class,
            failure_reason=failure_reason,
        )
        now = str(finalized_at or datetime.now(UTC).isoformat())
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            await self._ensure_initialized(conn)

            if summary is None and artifacts is None:
                await conn.execute(
                    """
                        UPDATE run_ledger
                        SET status = ?, failure_class = ?, failure_reason = ?, ended_at = ?, updated_at = ?
                        WHERE session_id = ?
                        """,
                    (
                        resolved_status,
                        failure_class,
                        failure_reason,
                        now,
                        now,
                        session_id,
                    ),
                )
            else:
                cursor = await conn.execute(
                    "SELECT summary_json, artifact_json FROM run_ledger WHERE session_id = ?",
                    (session_id,),
                )
                row = await cursor.fetchone()
                merged_summary: dict[str, Any] = {}
                merged_artifacts: dict[str, Any] = {}
                if row:
                    if row[0]:
                        try:
                            merged_summary = json.loads(row[0])
                        except json.JSONDecodeError:
                            merged_summary = {}
                    if row[1]:
                        try:
                            merged_artifacts = json.loads(row[1])
                        except json.JSONDecodeError:
                            merged_artifacts = {}
                if summary:
                    merged_summary.update(summary)
                if artifacts:
                    merged_artifacts.update(artifacts)

                await conn.execute(
                    """
                        UPDATE run_ledger
                        SET status = ?, failure_class = ?, failure_reason = ?, summary_json = ?, artifact_json = ?,
                            ended_at = ?, updated_at = ?
                        WHERE session_id = ?
                        """,
                    (
                        resolved_status,
                        failure_class,
                        failure_reason,
                        json.dumps(merged_summary),
                        json.dumps(merged_artifacts),
                        now,
                        now,
                        session_id,
                    ),
                )
            await conn.commit()

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'run_ledger'")).fetchone():
                return None
            cursor = await conn.execute("SELECT * FROM run_ledger WHERE session_id = ?", (session_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            for field in ("summary_json", "artifact_json"):
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except json.JSONDecodeError:
                        data[field] = str(data[field])
                else:
                    data[field] = {}
            return data
