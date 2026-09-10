from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import aiosqlite

from orket.adapters.storage.governed_agent_wake_control_support import (
    apply_cancellation_transaction,
    apply_recovery_transaction,
    list_action_records,
)
from orket.adapters.storage.governed_agent_wake_repository_support import ensure_schema
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeActionRecord,
    GovernedAgentWakeCancellationRequest,
    GovernedAgentWakeControlResult,
    GovernedAgentWakeRecoveryRequest,
)

ResultT = TypeVar("ResultT")


class AsyncGovernedAgentWakeControlRepository:
    """Durable operator-control receipts and wake transitions."""

    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def apply_cancellation(
        self,
        request: GovernedAgentWakeCancellationRequest,
    ) -> GovernedAgentWakeControlResult:
        return await self._execute(lambda conn: apply_cancellation_transaction(conn, request))

    async def apply_recovery(
        self,
        request: GovernedAgentWakeRecoveryRequest,
    ) -> GovernedAgentWakeControlResult:
        return await self._execute(lambda conn: apply_recovery_transaction(conn, request))

    async def list_actions(self, *, wake_id: str) -> tuple[GovernedAgentWakeActionRecord, ...]:
        return await self._execute(lambda conn: list_action_records(conn, wake_id=wake_id))

    async def _execute(self, operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]]) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await ensure_schema(conn)
                self._initialized = True
            result = await operation(conn)
            await conn.commit()
            return result
