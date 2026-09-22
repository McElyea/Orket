from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.control_plane_recovery_store import ControlPlaneRecoveryTransactionStore
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_effect_store import OutwardEffectTransactionStore, ensure_outward_effect_schema
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_model_admission_store import (
    OutwardModelAdmissionStore,
    ensure_outward_model_admission_schema,
)
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.control_plane_transaction import ControlPlaneTransaction
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

side_effecting = True


class OutwardStoreTransaction:
    """Explicit store operations sharing one owning transaction; contains no policy."""

    side_effecting = True

    def __init__(
        self,
        approvals: OutwardApprovalStore,
        runs: OutwardRunStore,
        events: OutwardRunEventStore,
        connection: aiosqlite.Connection,
    ) -> None:
        self._approvals, self._runs, self._events = approvals, runs, events
        self._connection = connection
        self.recovery = ControlPlaneRecoveryTransactionStore(connection)
        self.effects = OutwardEffectTransactionStore(connection)
        self.models = OutwardModelAdmissionStore(connection)
        self.ledger = OutwardLedgerSnapshotStore(runs.db_path, connection=connection)
        self.control_plane = ControlPlaneTransaction(
            execution=AsyncControlPlaneExecutionRepository(runs.db_path, connection=connection),
            records=AsyncControlPlaneRecordRepository(runs.db_path, connection=connection),
            pending_gates=AsyncPendingGateRepository(runs.db_path, connection=connection),
        )

    async def get_proposal(self, proposal_id: str) -> OutwardApprovalProposal | None:
        return await self._approvals.get(proposal_id, connection=self._connection)

    async def save_proposal(self, proposal: OutwardApprovalProposal) -> OutwardApprovalProposal:
        return await self._approvals.save(proposal, connection=self._connection)

    async def decide_proposal(self, proposal: OutwardApprovalProposal) -> bool:
        return await self._approvals.update_decision(proposal, connection=self._connection)

    async def count_proposals(self, run_id: str) -> int:
        return await self._approvals.count_for_run(run_id, connection=self._connection)

    async def get_run(self, run_id: str) -> OutwardRunRecord | None:
        return await self._runs.get(run_id, connection=self._connection)

    async def create_run(self, run: OutwardRunRecord) -> OutwardRunRecord:
        return await self._runs.create(run, connection=self._connection)

    async def get_active_by_namespace(self, namespace: str) -> OutwardRunRecord | None:
        return await self._runs.get_active_by_namespace(namespace, connection=self._connection)

    async def update_run(self, run: OutwardRunRecord) -> OutwardRunRecord:
        return await self._runs.update(run, connection=self._connection)

    async def append_event(self, event: LedgerEvent) -> LedgerEvent:
        return await self._events.append(event, connection=self._connection)

    async def get_event(self, event_id: str) -> LedgerEvent | None:
        return await self._events.get(event_id, connection=self._connection)


class OutwardStoreUnitOfWork:
    side_effecting = True

    @classmethod
    def for_run_stores(cls, runs: OutwardRunStore, events: OutwardRunEventStore) -> OutwardStoreUnitOfWork:
        return cls(approvals=OutwardApprovalStore(runs.db_path), runs=runs, events=events)

    def __init__(
        self,
        *,
        approvals: OutwardApprovalStore,
        runs: OutwardRunStore,
        events: OutwardRunEventStore,
    ) -> None:
        self._approvals, self._runs, self._events = approvals, runs, events

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[OutwardStoreTransaction]:
        stores = (self._approvals, self._runs, self._events)
        paths = [await asyncio.to_thread(store.db_path.resolve) for store in stores]
        if len(set(paths)) != 1:
            raise RuntimeError("E_OUTWARD_TRANSACTION_DATABASE_MISMATCH")
        for store in stores:
            await store.ensure_initialized()
        async with connect_sqlite_wal(paths[0]) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                await ensure_outward_effect_schema(connection)
                await ensure_outward_model_admission_schema(connection)
                yield OutwardStoreTransaction(*stores, connection)
                await connection.commit()
            finally:
                if connection.in_transaction:
                    await connection.rollback()
