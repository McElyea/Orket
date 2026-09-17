from __future__ import annotations

import aiosqlite

from orket.core.contracts import OperatorActionRecord

side_effecting = True


async def ensure_operator_action_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS operator_action_records (
            action_id TEXT PRIMARY KEY,
            target_ref TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operator_action_target
        ON operator_action_records (target_ref, timestamp)
        """
    )


async def operator_action_exists(conn: aiosqlite.Connection, *, action_id: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM operator_action_records WHERE action_id = ?",
        (action_id,),
    )
    return await cursor.fetchone() is not None


async def insert_operator_action(
    conn: aiosqlite.Connection,
    *,
    record: OperatorActionRecord,
) -> None:
    await conn.execute(
        """
        INSERT INTO operator_action_records (
            action_id, target_ref, timestamp, payload_json
        ) VALUES (?, ?, ?, ?)
        """,
        (
            record.action_id,
            record.target_ref,
            record.timestamp,
            record.model_dump_json(),
        ),
    )


async def get_operator_action(conn: aiosqlite.Connection, *, action_id: str) -> OperatorActionRecord | None:
    cursor = await conn.execute("SELECT payload_json FROM operator_action_records WHERE action_id = ?", (action_id,))
    row = await cursor.fetchone()
    return OperatorActionRecord.model_validate_json(str(row[0])) if row else None
