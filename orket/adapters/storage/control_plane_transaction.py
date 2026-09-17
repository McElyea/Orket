"""SQLite transaction spanning explicit execution and append-only record ports."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.control_plane_transaction import ControlPlaneTransaction


class SQLiteControlPlaneTransactions:
    side_effecting = True

    def __init__(self, db_path: str | Path):
        self.db_path = db_path

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[ControlPlaneTransaction]:
        async with connect_sqlite_wal(self.db_path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                yield ControlPlaneTransaction(
                    execution=AsyncControlPlaneExecutionRepository(self.db_path, connection=connection),
                    records=AsyncControlPlaneRecordRepository(self.db_path, connection=connection),
                    pending_gates=AsyncPendingGateRepository(self.db_path, connection=connection),
                )
                await connection.commit()
            finally:
                if connection.in_transaction:
                    await connection.rollback()
