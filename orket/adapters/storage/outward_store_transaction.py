from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

import aiosqlite

from orket.adapters.execution.owned_io import finish_owned_io, run_owned_io, run_owned_thread
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_file_tools import capture_file_roots
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
        *,
        db_path: Path,
    ) -> None:
        self._approvals, self._runs, self._events = approvals, runs, events
        self._connection = connection
        self.recovery = ControlPlaneRecoveryTransactionStore(connection)
        self.effects = OutwardEffectTransactionStore(connection)
        self.models = OutwardModelAdmissionStore(connection)
        self.ledger = OutwardLedgerSnapshotStore(db_path, connection=connection)
        self.control_plane = ControlPlaneTransaction(
            execution=AsyncControlPlaneExecutionRepository(db_path, connection=connection),
            records=AsyncControlPlaneRecordRepository(db_path, connection=connection),
            pending_gates=AsyncPendingGateRepository(db_path, connection=connection),
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
        selected_paths = capture_file_roots([store.db_path for store in stores])
        paths = await run_owned_thread(lambda: tuple(path.resolve() for path in selected_paths),
                                       label="outward-transaction-paths")
        if len(set(paths)) != 1:
            raise RuntimeError("E_OUTWARD_TRANSACTION_DATABASE_MISMATCH")
        initialization_stores: tuple[OutwardApprovalStore | OutwardRunStore | OutwardRunEventStore, ...] = stores
        for store, path in zip(initialization_stores, paths, strict=True):
            await store._ensure_initialized_at(path)
        stack = AsyncExitStack()
        connection: aiosqlite.Connection | None = None
        failure: BaseException | None = None
        try:
            opened_connection = await run_owned_io(lambda: stack.enter_async_context(connect_sqlite_wal(paths[0])),
                                                  label="outward-transaction-open", preserve_failure=True)
            connection = opened_connection
            await run_owned_io(lambda: self._prepare(opened_connection),
                               label="outward-transaction-prepare", preserve_failure=True)
            yield OutwardStoreTransaction(*stores, opened_connection, db_path=paths[0])
            await run_owned_io(opened_connection.commit, label="outward-transaction-commit", preserve_failure=True)
        except BaseException as error:  # Resource owner retains the selected body/admission failure through cleanup.
            failure = error
            raise
        finally:
            if failure is None:
                await run_owned_io(lambda: self._close(connection, stack),
                                   label="outward-transaction-close", preserve_failure=True)
            else:
                # Preserve a native cleanup failure, including CancelledError, while
                # discarding only later caller interruption of this selected failure.
                await finish_owned_io(lambda: self._close(connection, stack))

    @staticmethod
    async def _prepare(connection: aiosqlite.Connection) -> None:
        await connection.execute("BEGIN IMMEDIATE")
        await ensure_outward_effect_schema(connection)
        await ensure_outward_model_admission_schema(connection)

    @staticmethod
    async def _close(connection: aiosqlite.Connection | None, stack: AsyncExitStack) -> None:
        try:
            if connection is not None and connection.in_transaction:
                await connection.rollback()
        finally:
            await stack.aclose()
