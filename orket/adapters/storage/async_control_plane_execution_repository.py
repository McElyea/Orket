from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import aiosqlite

from orket.adapters.storage.sqlite_connection import sqlite_connection_scope
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain.control_plane_run_authority import same_run_admission
from orket.core.domain.control_plane_state_revision import (
    next_execution_record,
    read_execution_record,
    same_attempt_admission,
    same_step_admission,
)

ResultT = TypeVar("ResultT")


class ControlPlaneExecutionConflictError(ValueError):
    """Raised when a control-plane execution record cannot be updated truthfully."""


class AsyncControlPlaneExecutionRepository(ControlPlaneExecutionRepository):
    """Durable SQLite repository for current run and attempt authority."""

    side_effecting = True

    def __init__(self, db_path: str | Path, *, connection: aiosqlite.Connection | None = None) -> None:
        self.db_path = str(db_path)
        self._connection = connection
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_plane_runs (
                run_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_plane_attempts (
                attempt_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                attempt_ordinal INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_control_plane_attempts_run
            ON control_plane_attempts (run_id, attempt_ordinal)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS control_plane_steps (
                step_id TEXT PRIMARY KEY,
                attempt_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_control_plane_steps_attempt
            ON control_plane_steps (attempt_id, step_id)
            """
        )

    async def _execute(
        self,
        operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
        *,
        row_factory: bool = False,
        commit: bool = False,
    ) -> ResultT:
        async with self._lock, sqlite_connection_scope(self.db_path, self._connection, commit=commit) as conn:
            if row_factory:
                conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await self._ensure_initialized(conn)
                self._initialized = True
            result = await operation(conn)
            return result

    async def save_run_record(
        self,
        *,
        record: RunRecord,
    ) -> RunRecord:
        snapshot = RunRecord.model_validate(record.model_dump(warnings=False))

        async def _op(conn: aiosqlite.Connection) -> RunRecord:
            if not conn.in_transaction:
                await conn.execute("BEGIN IMMEDIATE")
            cursor = await conn.execute("SELECT payload_json FROM control_plane_runs WHERE run_id = ?", (snapshot.run_id,))
            row = await cursor.fetchone()
            existing = read_execution_record(RunRecord, row['payload_json']) if row is not None else None
            if existing is not None and not same_run_admission(existing, snapshot):
                raise ControlPlaneExecutionConflictError("E_CONTROL_PLANE_RUN_AUTHORITY_CONFLICT: immutable admission changed")
            saved = next_execution_record(existing, snapshot, ControlPlaneExecutionConflictError)
            if saved == existing:
                return saved
            await conn.execute(
                """
                INSERT INTO control_plane_runs (run_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (saved.run_id, saved.model_dump_json()),
            )
            return saved

        return await self._execute(_op, row_factory=True, commit=True)

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        async def _op(conn: aiosqlite.Connection) -> RunRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_runs WHERE run_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return read_execution_record(RunRecord, str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_attempt_record(
        self,
        *,
        record: AttemptRecord,
    ) -> AttemptRecord:
        snapshot = AttemptRecord.model_validate(record.model_dump(warnings=False))

        async def _op(conn: aiosqlite.Connection) -> AttemptRecord:
            if not conn.in_transaction:
                await conn.execute("BEGIN IMMEDIATE")
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_attempts WHERE attempt_id = ?",
                (snapshot.attempt_id,),
            )
            row = await cursor.fetchone()
            existing = read_execution_record(AttemptRecord, row['payload_json']) if row is not None else None
            if existing is not None and not same_attempt_admission(existing, snapshot):
                raise ControlPlaneExecutionConflictError("E_CONTROL_PLANE_ATTEMPT_AUTHORITY_CONFLICT: immutable admission changed")
            saved = next_execution_record(existing, snapshot, ControlPlaneExecutionConflictError)
            if saved == existing:
                return saved
            await conn.execute(
                """
                INSERT INTO control_plane_attempts (attempt_id, run_id, attempt_ordinal, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    saved.attempt_id,
                    saved.run_id,
                    saved.attempt_ordinal,
                    saved.model_dump_json(),
                ),
            )
            return saved

        return await self._execute(_op, row_factory=True, commit=True)

    async def get_attempt_record(self, *, attempt_id: str) -> AttemptRecord | None:
        async def _op(conn: aiosqlite.Connection) -> AttemptRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_attempts WHERE attempt_id = ?",
                (attempt_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return read_execution_record(AttemptRecord, str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_attempt_records(self, *, run_id: str) -> list[AttemptRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[AttemptRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM control_plane_attempts
                WHERE run_id = ?
                ORDER BY attempt_ordinal ASC
                """,
                (run_id,),
            )
            rows = await cursor.fetchall()
            return [read_execution_record(AttemptRecord, str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save_step_record(
        self,
        *,
        record: StepRecord,
    ) -> StepRecord:
        snapshot = StepRecord.model_validate(record.model_dump(warnings=False))

        async def _op(conn: aiosqlite.Connection) -> StepRecord:
            if not conn.in_transaction:
                await conn.execute("BEGIN IMMEDIATE")
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_steps WHERE step_id = ?",
                (snapshot.step_id,),
            )
            row = await cursor.fetchone()
            existing = read_execution_record(StepRecord, row['payload_json']) if row is not None else None
            if existing is not None and not same_step_admission(existing, snapshot):
                raise ControlPlaneExecutionConflictError("E_CONTROL_PLANE_STEP_AUTHORITY_CONFLICT: immutable admission changed")
            saved = next_execution_record(existing, snapshot, ControlPlaneExecutionConflictError)
            if saved == existing:
                return saved
            await conn.execute(
                """
                INSERT INTO control_plane_steps (step_id, attempt_id, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(step_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    saved.step_id,
                    saved.attempt_id,
                    saved.model_dump_json(),
                ),
            )
            return saved

        return await self._execute(_op, row_factory=True, commit=True)

    async def get_step_record(self, *, step_id: str) -> StepRecord | None:
        async def _op(conn: aiosqlite.Connection) -> StepRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_steps WHERE step_id = ?",
                (step_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return read_execution_record(StepRecord, str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_step_records(self, *, attempt_id: str) -> list[StepRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[StepRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM control_plane_steps
                WHERE attempt_id = ?
                ORDER BY step_id ASC
                """,
                (attempt_id,),
            )
            rows = await cursor.fetchall()
            return [read_execution_record(StepRecord, str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)


__all__ = [
    "AsyncControlPlaneExecutionRepository",
    "ControlPlaneExecutionConflictError",
]
