"""Serialize publication progress separately from the stores it publishes into."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from pathlib import Path
from typing import Literal, TypeVar

import aiosqlite

from orket.adapters.execution.owned_io import finish_owned_io, run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.epic_approval_pause_store import EpicApprovalPauseStore
from orket.adapters.storage.epic_export_dispatch_store import EpicExportDispatchStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.epic_publication import (
    EpicPreparationRecord,
    EpicPublicationRecord,
    EpicRunAdmission,
    EpicWorkloadOutcome,
    admission_transition_allowed,
)

RecordT = TypeVar("RecordT", EpicPublicationRecord, EpicPreparationRecord, EpicWorkloadOutcome, EpicRunAdmission)
JournalTable = Literal["epic_publications", "epic_preparations", "epic_workload_outcomes", "epic_run_admissions"]


side_effecting = True


class SQLiteEpicPublicationTransaction:
    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection, session_id: str):
        self.connection, self.session_id = connection, session_id
        self.approval_pauses = EpicApprovalPauseStore(connection, session_id)
        self.export_dispatch = EpicExportDispatchStore(connection, session_id)

    async def get(self) -> EpicPublicationRecord | None:
        return await self._load("epic_publications", EpicPublicationRecord, "PUBLICATION")

    async def save(self, record: EpicPublicationRecord) -> None:
        await self._save("epic_publications", record, await self.get(), "PUBLICATION")

    async def get_preparation(self) -> EpicPreparationRecord | None:
        return await self._load("epic_preparations", EpicPreparationRecord, "PREPARATION")

    async def save_preparation(self, record: EpicPreparationRecord) -> None:
        prior = await self.get_preparation()
        if prior is not None and (prior.policy != record.policy or prior.export_binding != record.export_binding):
            raise ValueError("E_EPIC_PREPARATION_CONFLICT")
        if prior is not None and prior.export_intent is not None and prior.export_intent != record.export_intent:
            raise ValueError("E_EPIC_EXPORT_INTENT_CONFLICT")
        await self._save("epic_preparations", record, prior, "PREPARATION")

    async def get_outcome(self) -> EpicWorkloadOutcome | None:
        return await self._load("epic_workload_outcomes", EpicWorkloadOutcome, "WORKLOAD_OUTCOME")

    async def save_outcome(self, record: EpicWorkloadOutcome) -> None:
        await self._save("epic_workload_outcomes", record, await self.get_outcome(), "WORKLOAD_OUTCOME")

    async def get_admission(self) -> EpicRunAdmission | None:
        return await self._load("epic_run_admissions", EpicRunAdmission, "ADMISSION")

    async def save_admission(self, record: EpicRunAdmission) -> None:
        record = EpicRunAdmission.model_validate_json(record.model_dump_json())
        await self._save("epic_run_admissions", record, await self.get_admission(), "ADMISSION")

    async def admission_conflicts(self, resources: list[str]) -> list[str]:
        conflicts = []
        # Validate retained rows before filtering: a damaged phase/resource projection
        # must not hide an active reservation. Stream history instead of loading it all.
        async with self.connection.execute("SELECT session_id, payload, digest FROM epic_run_admissions") as cursor:
            async for session_id, payload, digest in cursor:
                record = EpicRunAdmission.model_validate_json(payload)
                if record.session_id != session_id or record.digest() != digest:
                    raise ValueError("E_EPIC_ADMISSION_INTEGRITY")
                if record.phase == "released":
                    publication = await SQLiteEpicPublicationTransaction(self.connection, session_id).get()
                    if (publication is None or publication.phase != 4 or publication.plan.request != record.request
                            or publication.plan.ledger["artifacts"].get("epic_run_admission") != record.claim_ref()):
                        raise ValueError("E_EPIC_ADMISSION_RELEASE_UNCONFIRMED")
                if record.phase == "active" and set(resources).intersection(record.resources):
                    conflicts.append(session_id)
        return conflicts

    async def _load(self, table: JournalTable,
                    record_type: type[RecordT], kind: str) -> RecordT | None:
        # Table names come only from the fixed public methods; values remain bound parameters.
        row = await (await self.connection.execute(
            f"SELECT payload, digest FROM {table} WHERE session_id = ?", (self.session_id,))).fetchone()
        if row is None:
            return None
        record = record_type.model_validate_json(row[0])
        if self._record_session_id(record) != self.session_id or record.digest() != row[1]:
            raise ValueError(f"E_EPIC_{kind}_INTEGRITY")
        return record

    async def _save(self, table: JournalTable,
                    record: RecordT, prior: RecordT | None, kind: str) -> None:
        if self._record_session_id(record) != self.session_id:
            raise ValueError(f"E_EPIC_{kind}_SESSION")
        if prior is not None:
            if isinstance(record, EpicRunAdmission):
                conflict = not admission_transition_allowed(prior, record)
            else:
                conflict = (prior != record if isinstance(record, EpicWorkloadOutcome) else
                            prior.plan != record.plan or record.phase not in (prior.phase, prior.phase + 1))
            if conflict:
                raise ValueError(f"E_EPIC_{kind}_CONFLICT")
        if prior == record:
            return
        await self.connection.execute(
            f"INSERT INTO {table}(session_id, payload, digest) VALUES (?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload, digest=excluded.digest",
            (self.session_id, record.model_dump_json(), record.digest()))

    @staticmethod
    def _record_session_id(record: EpicPublicationRecord | EpicPreparationRecord | EpicWorkloadOutcome | EpicRunAdmission) -> str:
        return record.session_id if isinstance(record, (EpicWorkloadOutcome, EpicRunAdmission)) else record.plan.session_id


class SQLiteEpicPublicationRepository:
    side_effecting = True

    def __init__(self, runtime_db: str | Path):
        # A separate journal avoids holding the runtime DB write lock during its publication.
        self.db_path = Path(str(runtime_db) + ".epic-publications.sqlite3")

    @asynccontextmanager
    async def transaction(self, session_id: str) -> AsyncIterator[SQLiteEpicPublicationTransaction]:
        db_path, = capture_file_roots([self.db_path])
        await run_owned_thread(partial(db_path.parent.mkdir, parents=True, exist_ok=True),
                               label="epic-publication-parent")
        stack = AsyncExitStack()
        connection: aiosqlite.Connection | None = None
        failure: BaseException | None = None
        try:
            opened_connection = await run_owned_io(lambda: stack.enter_async_context(connect_sqlite_wal(db_path)),
                label="epic-publication-open", preserve_failure=True)
            connection = opened_connection
            await run_owned_io(lambda: self._prepare(opened_connection), label="epic-publication-prepare", preserve_failure=True)
            yield SQLiteEpicPublicationTransaction(opened_connection, session_id)
            await run_owned_io(opened_connection.commit, label="epic-publication-commit", preserve_failure=True)
        except BaseException as error:  # Resource owner: preserve the selected body/admission failure through cleanup.
            failure = error
            raise
        finally:
            if failure is None:
                await run_owned_io(lambda: self._close(connection, stack),
                                   label="epic-publication-close", preserve_failure=True)
            else:
                # Native cleanup cancellation is a failure, not later caller interruption.
                await finish_owned_io(lambda: self._close(connection, stack))

    @staticmethod
    async def _prepare(connection: aiosqlite.Connection) -> None:
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_publications ("
                                 "session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_preparations ("
                                 "session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_workload_outcomes ("
                                 "session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_run_admissions ("
                                 "session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        await connection.commit()
        await connection.execute("BEGIN IMMEDIATE")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_approval_pauses ("
                                 "session_id TEXT NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL, "
                                 "digest TEXT NOT NULL, PRIMARY KEY(session_id, sequence))")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_export_dispatches ("
                                 "session_id TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
        await connection.execute("CREATE TABLE IF NOT EXISTS epic_approval_recoveries ("
                                 "session_id TEXT NOT NULL, sequence INTEGER NOT NULL, ordinal INTEGER NOT NULL, "
                                 "request_id TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, "
                                 "PRIMARY KEY(session_id, sequence, ordinal), UNIQUE(session_id, request_id))")

    @staticmethod
    async def _close(connection: aiosqlite.Connection | None, stack: AsyncExitStack) -> None:
        try:
            if connection is not None and connection.in_transaction:
                await connection.rollback()
        finally:
            await stack.aclose()
