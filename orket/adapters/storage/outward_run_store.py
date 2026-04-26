from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigration, SQLiteMigrationRunner
from orket.core.domain.outward_runs import OutwardRunRecord

_ACTIVE_STATUSES = frozenset({"queued", "running", "approval_required"})

_MIGRATIONS = [
    SQLiteMigration(
        version=1,
        name="create_outward_runs",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS outward_runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                namespace TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                stop_reason TEXT,
                current_turn INTEGER NOT NULL,
                max_turns INTEGER NOT NULL,
                task_json TEXT NOT NULL,
                policy_overrides_json TEXT NOT NULL,
                pending_proposals_json TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_outward_runs_status ON outward_runs (status)",
            "CREATE INDEX IF NOT EXISTS idx_outward_runs_namespace ON outward_runs (namespace)",
            "CREATE INDEX IF NOT EXISTS idx_outward_runs_submitted_at ON outward_runs (submitted_at)",
        ),
    )
]


class OutwardRunStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            async with connect_sqlite_wal(self.db_path) as conn:
                await SQLiteMigrationRunner(namespace="outward_runs").apply(conn, _MIGRATIONS)
                await conn.commit()
            self._initialized = True

    async def create(self, record: OutwardRunRecord) -> OutwardRunRecord:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO outward_runs (
                    run_id, status, namespace, submitted_at, started_at, completed_at, stop_reason,
                    current_turn, max_turns, task_json, policy_overrides_json, pending_proposals_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _record_params(record),
            )
            await conn.commit()
        return record

    async def update(self, record: OutwardRunRecord) -> OutwardRunRecord:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE outward_runs
                SET status = ?,
                    namespace = ?,
                    submitted_at = ?,
                    started_at = ?,
                    completed_at = ?,
                    stop_reason = ?,
                    current_turn = ?,
                    max_turns = ?,
                    task_json = ?,
                    policy_overrides_json = ?,
                    pending_proposals_json = ?
                WHERE run_id = ?
                """,
                (
                    record.status,
                    record.namespace,
                    record.submitted_at,
                    record.started_at,
                    record.completed_at,
                    record.stop_reason,
                    record.current_turn,
                    record.max_turns,
                    _json(record.task),
                    _json(record.policy_overrides),
                    _json(list(record.pending_proposals)),
                    record.run_id,
                ),
            )
            await conn.commit()
        return record

    async def get(self, run_id: str) -> OutwardRunRecord | None:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM outward_runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_active_by_namespace(self, namespace: str) -> OutwardRunRecord | None:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM outward_runs
                WHERE namespace = ? AND status IN (?, ?, ?)
                ORDER BY submitted_at ASC, run_id ASC
                LIMIT 1
                """,
                (namespace, *_ACTIVE_STATUSES),
            )
            row = await cursor.fetchone()
        return _row_to_record(row) if row is not None else None

    async def list(self, *, status: str | None = None, limit: int = 20, offset: int = 0) -> list[OutwardRunRecord]:
        await self.ensure_initialized()
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if status:
                cursor = await conn.execute(
                    """
                    SELECT * FROM outward_runs
                    WHERE status = ?
                    ORDER BY submitted_at DESC, run_id ASC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM outward_runs
                    ORDER BY submitted_at DESC, run_id ASC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]


def _record_params(record: OutwardRunRecord) -> tuple[Any, ...]:
    return (
        record.run_id,
        record.status,
        record.namespace,
        record.submitted_at,
        record.started_at,
        record.completed_at,
        record.stop_reason,
        record.current_turn,
        record.max_turns,
        _json(record.task),
        _json(record.policy_overrides),
        _json(list(record.pending_proposals)),
    )


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _row_to_record(row: aiosqlite.Row) -> OutwardRunRecord:
    return OutwardRunRecord(
        run_id=str(row["run_id"]),
        status=str(row["status"]),
        namespace=str(row["namespace"]),
        submitted_at=str(row["submitted_at"]),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        stop_reason=row["stop_reason"],
        current_turn=int(row["current_turn"]),
        max_turns=int(row["max_turns"]),
        task=dict(json.loads(str(row["task_json"]))),
        policy_overrides=dict(json.loads(str(row["policy_overrides_json"]))),
        pending_proposals=tuple(dict(item) for item in json.loads(str(row["pending_proposals_json"]))),
    )


__all__ = ["OutwardRunStore"]
