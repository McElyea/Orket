from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.contracts.control_plane_effect_journal_models import (
    CheckpointAcceptanceRecord,
    EffectJournalEntryRecord,
)
from orket.core.contracts.control_plane_models import (
    CheckpointRecord,
    FinalTruthRecord,
    LeaseRecord,
    OperatorActionRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
    ReservationRecord,
    ResolvedConfigurationSnapshot,
    ResolvedPolicySnapshot,
    ResourceRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository

ResultT = TypeVar("ResultT")


class ControlPlaneRecordConflictError(ValueError):
    """Raised when a control-plane record id is reused with different content."""


class AsyncControlPlaneRecordRepository(ControlPlaneRecordRepository):
    """Durable SQLite repository for append-only ControlPlane records."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resolved_policy_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resolved_configuration_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reservation_records (
                reservation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                creation_timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (reservation_id, status)
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reservation_records_creation
            ON reservation_records (creation_timestamp)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resource_records (
                resource_id TEXT NOT NULL,
                last_observed_timestamp TEXT NOT NULL,
                current_observed_state TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (resource_id, last_observed_timestamp, current_observed_state)
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_resource_records_latest
            ON resource_records (resource_id, last_observed_timestamp DESC, current_observed_state DESC)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS effect_journal_entries (
                journal_entry_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                publication_sequence INTEGER NOT NULL,
                entry_digest TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_effect_journal_run_sequence
            ON effect_journal_entries (run_id, publication_sequence)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoint_records (
                checkpoint_id TEXT PRIMARY KEY,
                parent_ref TEXT NOT NULL,
                creation_timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_checkpoint_records_parent
            ON checkpoint_records (parent_ref, creation_timestamp)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoint_acceptance_records (
                acceptance_id TEXT PRIMARY KEY,
                checkpoint_id TEXT NOT NULL,
                decision_timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_checkpoint_acceptance_checkpoint
            ON checkpoint_acceptance_records (checkpoint_id, decision_timestamp)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_decision_records (
                decision_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lease_records (
                lease_id TEXT NOT NULL,
                lease_epoch INTEGER NOT NULL,
                status TEXT NOT NULL,
                publication_timestamp TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (lease_id, lease_epoch, status, publication_timestamp)
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_lease_records_latest
            ON lease_records (lease_id, lease_epoch DESC, publication_timestamp DESC)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_lease_records_resource
            ON lease_records (resource_id, publication_timestamp)
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reconciliation_records (
                reconciliation_id TEXT PRIMARY KEY,
                target_ref TEXT NOT NULL,
                publication_timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reconciliation_target
            ON reconciliation_records (target_ref, publication_timestamp)
            """
        )
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
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS final_truth_records (
                final_truth_record_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_final_truth_run
            ON final_truth_records (run_id, final_truth_record_id)
            """
        )

    async def _execute(
        self,
        operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
        *,
        row_factory: bool = False,
        commit: bool = False,
    ) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            if row_factory:
                conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await self._ensure_initialized(conn)
                self._initialized = True
            result = await operation(conn)
            if commit:
                await conn.commit()
            return result

    async def _insert_or_return_existing(
        self,
        *,
        table: str,
        id_field: str,
        id_value: str,
        payload_json: str,
        insert_op: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
        parse_existing: Callable[[str], ResultT],
    ) -> ResultT:
        async def _op(conn: aiosqlite.Connection) -> ResultT:
            cursor = await conn.execute(f"SELECT payload_json FROM {table} WHERE {id_field} = ?", (id_value,))
            existing = await cursor.fetchone()
            if existing is not None:
                existing_payload = str(existing["payload_json"] if isinstance(existing, aiosqlite.Row) else existing[0])
                if existing_payload != payload_json:
                    raise ControlPlaneRecordConflictError(f"{table}.{id_field} reused with different payload")
                return parse_existing(existing_payload)
            return await insert_op(conn)

        return await self._execute(_op, row_factory=True, commit=True)

    async def save_resolved_policy_snapshot(
        self,
        *,
        snapshot: ResolvedPolicySnapshot,
    ) -> ResolvedPolicySnapshot:
        payload_json = snapshot.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> ResolvedPolicySnapshot:
            await conn.execute(
                """
                INSERT INTO resolved_policy_snapshots (
                    snapshot_id, created_at, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.created_at,
                    payload_json,
                ),
            )
            return snapshot

        return await self._insert_or_return_existing(
            table="resolved_policy_snapshots",
            id_field="snapshot_id",
            id_value=snapshot.snapshot_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=ResolvedPolicySnapshot.model_validate_json,
        )

    async def get_resolved_policy_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> ResolvedPolicySnapshot | None:
        async def _op(conn: aiosqlite.Connection) -> ResolvedPolicySnapshot | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM resolved_policy_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ResolvedPolicySnapshot.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_resolved_configuration_snapshot(
        self,
        *,
        snapshot: ResolvedConfigurationSnapshot,
    ) -> ResolvedConfigurationSnapshot:
        payload_json = snapshot.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> ResolvedConfigurationSnapshot:
            await conn.execute(
                """
                INSERT INTO resolved_configuration_snapshots (
                    snapshot_id, created_at, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.created_at,
                    payload_json,
                ),
            )
            return snapshot

        return await self._insert_or_return_existing(
            table="resolved_configuration_snapshots",
            id_field="snapshot_id",
            id_value=snapshot.snapshot_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=ResolvedConfigurationSnapshot.model_validate_json,
        )

    async def get_resolved_configuration_snapshot(
        self,
        *,
        snapshot_id: str,
    ) -> ResolvedConfigurationSnapshot | None:
        async def _op(conn: aiosqlite.Connection) -> ResolvedConfigurationSnapshot | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM resolved_configuration_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ResolvedConfigurationSnapshot.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_reservation_record(
        self,
        *,
        record: ReservationRecord,
    ) -> ReservationRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> ReservationRecord:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reservation_records
                WHERE reservation_id = ? AND status = ?
                """,
                (
                    record.reservation_id,
                    record.status.value,
                ),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                existing_payload = str(existing["payload_json"] if isinstance(existing, aiosqlite.Row) else existing[0])
                if existing_payload != payload_json:
                    raise ControlPlaneRecordConflictError(
                        "reservation_records composite key reused with different payload"
                    )
                return ReservationRecord.model_validate_json(existing_payload)
            await conn.execute(
                """
                INSERT INTO reservation_records (
                    reservation_id, status, creation_timestamp, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.reservation_id,
                    record.status.value,
                    record.creation_timestamp,
                    payload_json,
                ),
            )
            return record

        return await self._execute(_op, row_factory=True, commit=True)

    async def list_reservation_records(self, *, reservation_id: str) -> list[ReservationRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[ReservationRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reservation_records
                WHERE reservation_id = ?
                ORDER BY rowid ASC
                """,
                (reservation_id,),
            )
            rows = await cursor.fetchall()
            return [ReservationRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def get_latest_reservation_record(self, *, reservation_id: str) -> ReservationRecord | None:
        async def _op(conn: aiosqlite.Connection) -> ReservationRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reservation_records
                WHERE reservation_id = ?
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (reservation_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ReservationRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_reservation_records_for_holder_ref(self, *, holder_ref: str) -> list[ReservationRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[ReservationRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reservation_records
                ORDER BY creation_timestamp ASC, reservation_id ASC, rowid ASC
                """
            )
            rows = await cursor.fetchall()
            records = [ReservationRecord.model_validate_json(str(row["payload_json"])) for row in rows]
            return [record for record in records if record.holder_ref == holder_ref]

        return await self._execute(_op, row_factory=True)

    async def get_latest_reservation_record_for_holder_ref(self, *, holder_ref: str) -> ReservationRecord | None:
        records = await self.list_reservation_records_for_holder_ref(holder_ref=holder_ref)
        return records[-1] if records else None

    async def save_resource_record(
        self,
        *,
        record: ResourceRecord,
    ) -> ResourceRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> ResourceRecord:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM resource_records
                WHERE resource_id = ? AND last_observed_timestamp = ? AND current_observed_state = ?
                """,
                (
                    record.resource_id,
                    record.last_observed_timestamp,
                    record.current_observed_state,
                ),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                existing_payload = str(existing["payload_json"] if isinstance(existing, aiosqlite.Row) else existing[0])
                if existing_payload != payload_json:
                    raise ControlPlaneRecordConflictError(
                        "resource_records composite key reused with different payload"
                    )
                return ResourceRecord.model_validate_json(existing_payload)
            await conn.execute(
                """
                INSERT INTO resource_records (
                    resource_id, last_observed_timestamp, current_observed_state, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.resource_id,
                    record.last_observed_timestamp,
                    record.current_observed_state,
                    payload_json,
                ),
            )
            return record

        return await self._execute(_op, row_factory=True, commit=True)

    async def list_resource_records(self, *, resource_id: str) -> list[ResourceRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[ResourceRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM resource_records
                WHERE resource_id = ?
                ORDER BY rowid ASC
                """,
                (resource_id,),
            )
            rows = await cursor.fetchall()
            return [ResourceRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def get_latest_resource_record(self, *, resource_id: str) -> ResourceRecord | None:
        async def _op(conn: aiosqlite.Connection) -> ResourceRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM resource_records
                WHERE resource_id = ?
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (resource_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ResourceRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def append_effect_journal_entry(
        self,
        *,
        run_id: str,
        entry: EffectJournalEntryRecord,
    ) -> EffectJournalEntryRecord:
        payload_json = entry.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> EffectJournalEntryRecord:
            await conn.execute(
                """
                INSERT INTO effect_journal_entries (
                    journal_entry_id, run_id, publication_sequence, entry_digest, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.journal_entry_id,
                    run_id,
                    entry.publication_sequence,
                    entry.entry_digest,
                    payload_json,
                ),
            )
            return entry

        return await self._insert_or_return_existing(
            table="effect_journal_entries",
            id_field="journal_entry_id",
            id_value=entry.journal_entry_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=EffectJournalEntryRecord.model_validate_json,
        )

    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[EffectJournalEntryRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM effect_journal_entries
                WHERE run_id = ?
                ORDER BY publication_sequence ASC
                """,
                (run_id,),
            )
            rows = await cursor.fetchall()
            return [EffectJournalEntryRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save_checkpoint(
        self,
        *,
        record: CheckpointRecord,
    ) -> CheckpointRecord:
        payload_json = record.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> CheckpointRecord:
            await conn.execute(
                """
                INSERT INTO checkpoint_records (
                    checkpoint_id, parent_ref, creation_timestamp, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.checkpoint_id,
                    record.parent_ref,
                    record.creation_timestamp,
                    payload_json,
                ),
            )
            return record

        return await self._insert_or_return_existing(
            table="checkpoint_records",
            id_field="checkpoint_id",
            id_value=record.checkpoint_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=CheckpointRecord.model_validate_json,
        )

    async def get_checkpoint(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        async def _op(conn: aiosqlite.Connection) -> CheckpointRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM checkpoint_records WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return CheckpointRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_checkpoints(self, *, parent_ref: str) -> list[CheckpointRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[CheckpointRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM checkpoint_records
                WHERE parent_ref = ?
                ORDER BY creation_timestamp ASC, checkpoint_id ASC
                """,
                (parent_ref,),
            )
            rows = await cursor.fetchall()
            return [CheckpointRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord:
        payload_json = acceptance.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> CheckpointAcceptanceRecord:
            await conn.execute(
                """
                INSERT INTO checkpoint_acceptance_records (
                    acceptance_id, checkpoint_id, decision_timestamp, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    acceptance.acceptance_id,
                    acceptance.checkpoint_id,
                    acceptance.decision_timestamp,
                    payload_json,
                ),
            )
            return acceptance

        return await self._insert_or_return_existing(
            table="checkpoint_acceptance_records",
            id_field="acceptance_id",
            id_value=acceptance.acceptance_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=CheckpointAcceptanceRecord.model_validate_json,
        )

    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None:
        async def _op(conn: aiosqlite.Connection) -> CheckpointAcceptanceRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM checkpoint_acceptance_records
                WHERE checkpoint_id = ?
                ORDER BY decision_timestamp DESC, acceptance_id DESC
                LIMIT 1
                """,
                (checkpoint_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return CheckpointAcceptanceRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord:
        payload_json = decision.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> RecoveryDecisionRecord:
            await conn.execute(
                """
                INSERT INTO recovery_decision_records (
                    decision_id, run_id, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    decision.decision_id,
                    decision.run_id,
                    payload_json,
                ),
            )
            return decision

        return await self._insert_or_return_existing(
            table="recovery_decision_records",
            id_field="decision_id",
            id_value=decision.decision_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=RecoveryDecisionRecord.model_validate_json,
        )

    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None:
        async def _op(conn: aiosqlite.Connection) -> RecoveryDecisionRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM recovery_decision_records WHERE decision_id = ?",
                (decision_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return RecoveryDecisionRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def append_lease_record(
        self,
        *,
        record: LeaseRecord,
    ) -> LeaseRecord:
        payload_json = record.model_dump_json()

        async def _op(conn: aiosqlite.Connection) -> LeaseRecord:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM lease_records
                WHERE lease_id = ? AND lease_epoch = ? AND status = ? AND publication_timestamp = ?
                """,
                (
                    record.lease_id,
                    record.lease_epoch,
                    record.status.value,
                    record.publication_timestamp,
                ),
            )
            existing = await cursor.fetchone()
            if existing is not None:
                existing_payload = str(existing["payload_json"] if isinstance(existing, aiosqlite.Row) else existing[0])
                if existing_payload != payload_json:
                    raise ControlPlaneRecordConflictError("lease_records composite key reused with different payload")
                return LeaseRecord.model_validate_json(existing_payload)
            await conn.execute(
                """
                INSERT INTO lease_records (
                    lease_id, lease_epoch, status, publication_timestamp, resource_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.lease_id,
                    record.lease_epoch,
                    record.status.value,
                    record.publication_timestamp,
                    record.resource_id,
                    payload_json,
                ),
            )
            return record

        return await self._execute(_op, row_factory=True, commit=True)

    async def list_lease_records(self, *, lease_id: str) -> list[LeaseRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[LeaseRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM lease_records
                WHERE lease_id = ?
                ORDER BY lease_epoch ASC, publication_timestamp ASC, rowid ASC
                """,
                (lease_id,),
            )
            rows = await cursor.fetchall()
            return [LeaseRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def get_latest_lease_record(self, *, lease_id: str) -> LeaseRecord | None:
        async def _op(conn: aiosqlite.Connection) -> LeaseRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM lease_records
                WHERE lease_id = ?
                ORDER BY lease_epoch DESC, publication_timestamp DESC, rowid DESC
                LIMIT 1
                """,
                (lease_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return LeaseRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_reconciliation_record(
        self,
        *,
        record: ReconciliationRecord,
    ) -> ReconciliationRecord:
        payload_json = record.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> ReconciliationRecord:
            await conn.execute(
                """
                INSERT INTO reconciliation_records (
                    reconciliation_id, target_ref, publication_timestamp, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.reconciliation_id,
                    record.target_ref,
                    record.publication_timestamp,
                    payload_json,
                ),
            )
            return record

        return await self._insert_or_return_existing(
            table="reconciliation_records",
            id_field="reconciliation_id",
            id_value=record.reconciliation_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=ReconciliationRecord.model_validate_json,
        )

    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None:
        async def _op(conn: aiosqlite.Connection) -> ReconciliationRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM reconciliation_records WHERE reconciliation_id = ?",
                (reconciliation_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ReconciliationRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_reconciliation_records(self, *, target_ref: str) -> list[ReconciliationRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[ReconciliationRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reconciliation_records
                WHERE target_ref = ?
                ORDER BY publication_timestamp ASC, reconciliation_id ASC
                """,
                (target_ref,),
            )
            rows = await cursor.fetchall()
            return [ReconciliationRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def get_latest_reconciliation_record(self, *, target_ref: str) -> ReconciliationRecord | None:
        async def _op(conn: aiosqlite.Connection) -> ReconciliationRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM reconciliation_records
                WHERE target_ref = ?
                ORDER BY publication_timestamp DESC, reconciliation_id DESC
                LIMIT 1
                """,
                (target_ref,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return ReconciliationRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def save_operator_action(
        self,
        *,
        record: OperatorActionRecord,
    ) -> OperatorActionRecord:
        payload_json = record.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> OperatorActionRecord:
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
                    payload_json,
                ),
            )
            return record

        return await self._insert_or_return_existing(
            table="operator_action_records",
            id_field="action_id",
            id_value=record.action_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=OperatorActionRecord.model_validate_json,
        )

    async def get_operator_action(self, *, action_id: str) -> OperatorActionRecord | None:
        async def _op(conn: aiosqlite.Connection) -> OperatorActionRecord | None:
            cursor = await conn.execute(
                "SELECT payload_json FROM operator_action_records WHERE action_id = ?",
                (action_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return OperatorActionRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)

    async def list_operator_actions(self, *, target_ref: str) -> list[OperatorActionRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[OperatorActionRecord]:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM operator_action_records
                WHERE target_ref = ?
                ORDER BY timestamp ASC, action_id ASC
                """,
                (target_ref,),
            )
            rows = await cursor.fetchall()
            return [OperatorActionRecord.model_validate_json(str(row["payload_json"])) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord:
        payload_json = record.model_dump_json()

        async def _insert(conn: aiosqlite.Connection) -> FinalTruthRecord:
            await conn.execute(
                """
                INSERT INTO final_truth_records (
                    final_truth_record_id, run_id, payload_json
                ) VALUES (?, ?, ?)
                """,
                (
                    record.final_truth_record_id,
                    record.run_id,
                    payload_json,
                ),
            )
            return record

        return await self._insert_or_return_existing(
            table="final_truth_records",
            id_field="final_truth_record_id",
            id_value=record.final_truth_record_id,
            payload_json=payload_json,
            insert_op=_insert,
            parse_existing=FinalTruthRecord.model_validate_json,
        )

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        async def _op(conn: aiosqlite.Connection) -> FinalTruthRecord | None:
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM final_truth_records
                WHERE run_id = ?
                ORDER BY final_truth_record_id DESC
                LIMIT 1
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return FinalTruthRecord.model_validate_json(str(row["payload_json"]))

        return await self._execute(_op, row_factory=True)


__all__ = [
    "AsyncControlPlaneRecordRepository",
    "ControlPlaneRecordConflictError",
]
