from __future__ import annotations

import aiosqlite

from orket.adapters.storage.control_plane_operator_action_support import get_operator_action, insert_operator_action
from orket.core.contracts.control_plane_models import OperatorActionRecord, RecoveryDecisionRecord

side_effecting = True


async def ensure_recovery_decision_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute("""CREATE TABLE IF NOT EXISTS recovery_decision_records (
        decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, payload_json TEXT NOT NULL
    )""")


async def insert_recovery_decision(conn: aiosqlite.Connection, *, decision: RecoveryDecisionRecord) -> RecoveryDecisionRecord:
    await conn.execute("""INSERT INTO recovery_decision_records (decision_id, run_id, payload_json)
        VALUES (?, ?, ?)""", (decision.decision_id, decision.run_id, decision.model_dump_json()))
    return decision


async def get_recovery_decision(conn: aiosqlite.Connection, *, decision_id: str) -> RecoveryDecisionRecord | None:
    cursor = await conn.execute("SELECT payload_json FROM recovery_decision_records WHERE decision_id = ?", (decision_id,))
    row = await cursor.fetchone()
    return RecoveryDecisionRecord.model_validate_json(str(row[0])) if row else None


class ControlPlaneRecoveryTransactionStore:
    """Paired recovery decision/operator writes owned by the caller's transaction."""

    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get(self, decision_id: str) -> tuple[RecoveryDecisionRecord, OperatorActionRecord] | None:
        decision = await get_recovery_decision(self.connection, decision_id=decision_id)
        action = await get_operator_action(self.connection, action_id=decision_id)
        if (decision is None) != (action is None):
            raise RuntimeError("E_OUTWARD_RECOVERY_RECORD_INCOMPLETE")
        return (decision, action) if decision is not None else None

    async def save(self, decision: RecoveryDecisionRecord, action: OperatorActionRecord) -> None:
        await insert_recovery_decision(self.connection, decision=decision)
        await insert_operator_action(self.connection, record=action)
