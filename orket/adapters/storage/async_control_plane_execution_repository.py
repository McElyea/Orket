from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import aiosqlite

from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository

ResultT = TypeVar("ResultT")


class ControlPlaneExecutionConflictError(ValueError):
    """Raised when a control-plane execution record cannot be updated truthfully."""


class AsyncControlPlaneExecutionRepository(ControlPlaneExecutionRepository):
    """Durable SQLite repository for current run and attempt authority."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
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
        async with self._lock, aiosqlite.connect(self.db_path) as conn:
            if row_factory:
                conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await self._ensure_initialized(conn)
                self._initialized = True
            result = await operation(conn)
            if commit:
                await conn.commit()
            return result

    async def save_run_record(
        self,
        *,
        record: RunRecord,
    ) -> RunRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> RunRecord:
            await conn.execute(
                """
                INSERT INTO control_plane_runs (run_id, payload_json)
                VALUES (?, ?)
                ON CONFLICT(run_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (record.run_id, payload_json),
            )
            return record

        return await self._execute(_op, commit=True)

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        async def _op(conn: aiosqlite.Connection) -> RunRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM control_plane_runs WHERE run_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return RunRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_attempt_record(
        self,
        *,
        record: AttemptRecord,
    ) -> AttemptRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> AttemptRecord:
            cursor = await conn.execute(
                "SELECT run_id, attempt_ordinal FROM control_plane_attempts WHERE attempt_id = ?",
                (record.attempt_id,),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                existing_run_id = str(existing["run_id"])
                existing_attempt_ordinal = int(existing["attempt_ordinal"])
                if existing_run_id != record.run_id or existing_attempt_ordinal != record.attempt_ordinal:
                    raise ControlPlaneExecutionConflictError(
                        "attempt_id reused with different run_id or attempt_ordinal"
                    )
            await conn.execute(
                """
                INSERT INTO control_plane_attempts (attempt_id, run_id, attempt_ordinal, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(attempt_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    record.attempt_id,
                    record.run_id,
                    record.attempt_ordinal,
                    payload_json,
                ),
            )
            return record

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
            return AttemptRecord.model_validate_json(str(row["payload_json"]))

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
            return [AttemptRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save_step_record(
        self,
        *,
        record: StepRecord,
    ) -> StepRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> StepRecord:
            cursor = await conn.execute(
                "SELECT attempt_id FROM control_plane_steps WHERE step_id = ?",
                (record.step_id,),
            )
            existing = await cursor.fetchone()
            if existing is not None and str(existing["attempt_id"]) != record.attempt_id:
                raise ControlPlaneExecutionConflictError("step_id reused with different attempt_id")
            await conn.execute(
                """
                INSERT INTO control_plane_steps (step_id, attempt_id, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(step_id) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (
                    record.step_id,
                    record.attempt_id,
                    payload_json,
                ),
            )
            return record

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
            return StepRecord.model_validate_json(str(row["payload_json"]))

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
            return [StepRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)


__all__ = [
    "AsyncControlPlaneExecutionRepository",
    "ControlPlaneExecutionConflictError",
]
