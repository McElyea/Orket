from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from orket.adapters.storage.control_plane_operator_action_support import (
    ensure_operator_action_schema,
    insert_operator_action,
)
from orket.adapters.storage.governed_agent_repository_support import ensure_governed_agent_schema
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts import OperatorActionRecord

side_effecting = True


async def agent_control_actions(conn: aiosqlite.Connection, invocation_id: str) -> tuple[OperatorActionRecord, ...]:
    await ensure_operator_action_schema(conn)
    cursor = await conn.execute(
        "SELECT payload_json FROM operator_action_records WHERE "
        "json_extract(payload_json, '$.precondition_basis_ref') = ? ORDER BY action_id",
        (f"agent-control:{invocation_id}",),
    )
    return tuple(OperatorActionRecord.model_validate_json(row[0]) for row in await cursor.fetchall())


class AsyncGovernedAgentRunControlRepository:
    """Persist existing operator-action authority atomically against the iteration decision boundary."""

    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def list_controls(self, invocation_id: str) -> tuple[OperatorActionRecord, ...]:
        async with connect_sqlite_wal(self._db_path) as conn:
            return await agent_control_actions(conn, invocation_id)

    async def submit(self, invocation_id: str, action: OperatorActionRecord) -> str:
        async with connect_sqlite_wal(self._db_path) as conn:
            await ensure_governed_agent_schema(conn)
            await ensure_operator_action_schema(conn)
            await conn.execute("BEGIN IMMEDIATE")
            existing = await conn.execute("SELECT payload_json FROM operator_action_records WHERE action_id=?",
                                          (action.action_id,))
            row = await existing.fetchone()
            if row is not None:
                return "idempotent" if OperatorActionRecord.model_validate_json(row[0]) == action else "conflict"
            cursor = await conn.execute(
                "SELECT binding_json,decision_json,state FROM governed_agent_invocations WHERE invocation_id=?",
                (invocation_id,),
            )
            row = await cursor.fetchone()
            if row is None or row[1] is not None or row[2] not in {"prepared", "returned"}:
                return "too_late"
            binding = json.loads(row[0])
            cursor = await conn.execute("SELECT payload_json FROM control_plane_runs WHERE run_id=?",
                                        (action.target_ref,))
            run_row = await cursor.fetchone()
            if (binding["run_id"] != action.target_ref or run_row is None
                    or json.loads(run_row[0])["lifecycle_state"] != "executing"):
                return "conflict"
            controls = await agent_control_actions(conn, invocation_id)
            if any(item.command_class == action.command_class for item in controls):
                return "conflict"
            await insert_operator_action(conn, record=action)
            await conn.commit()
            return "requested"
