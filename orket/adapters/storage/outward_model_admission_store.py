from __future__ import annotations

from dataclasses import asdict

import aiosqlite

from orket.adapters.storage.outward_model_admission_migrations import OUTWARD_MODEL_ADMISSION_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.domain.outward_model_admission import OutwardModelAdmission


async def ensure_outward_model_admission_schema(connection: aiosqlite.Connection) -> None:
    await SQLiteMigrationRunner(namespace="outward_model_admissions").apply(connection, OUTWARD_MODEL_ADMISSION_MIGRATIONS)


class OutwardModelAdmissionStore:
    """Transaction-bound persistence; application owns admission and recovery policy."""

    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get(self, run_id: str, generation: int, turn: int, step_index: int) -> OutwardModelAdmission | None:
        async with self.connection.execute(
            "SELECT * FROM outward_model_attempts_v2 WHERE run_id = ? AND execution_generation = ? AND turn = ? AND step_index = ? ORDER BY fencing_generation DESC LIMIT 1",
            (run_id, generation, turn, step_index),
        ) as cursor:
            row = await cursor.fetchone()
            return OutwardModelAdmission(**dict(zip([column[0] for column in cursor.description], row, strict=True))) if row else None

    async def list_attempts(self, run_id: str, generation: int, turn: int, step_index: int) -> list[OutwardModelAdmission]:
        async with self.connection.execute(
            "SELECT * FROM outward_model_attempts_v2 WHERE run_id = ? AND execution_generation = ? AND turn = ? "
            "AND step_index = ? ORDER BY fencing_generation",
            (run_id, generation, turn, step_index),
        ) as cursor:
            columns = [column[0] for column in cursor.description]
            return [OutwardModelAdmission(**dict(zip(columns, row, strict=True))) for row in await cursor.fetchall()]

    async def create(self, admission: OutwardModelAdmission) -> None:
        values = asdict(admission)
        await self.connection.execute(
            f"INSERT INTO outward_model_attempts_v2 ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )

    async def transition(self, previous: OutwardModelAdmission, updated: OutwardModelAdmission) -> None:
        values = asdict(updated)
        cursor = await self.connection.execute(
            f"UPDATE outward_model_attempts_v2 SET {', '.join(f'{key} = ?' for key in values)} "
            "WHERE run_id = ? AND execution_generation = ? AND turn = ? AND step_index = ? AND state = ? "
            "AND owner_id IS ? AND inputs_digest = ? AND result_digest IS ? AND fencing_generation = ?",
            (*values.values(), previous.run_id, previous.execution_generation, previous.turn, previous.step_index,
             previous.state, previous.owner_id, previous.inputs_digest, previous.result_digest, previous.fencing_generation),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("E_OUTWARD_MODEL_ADMISSION_CONFLICT")
