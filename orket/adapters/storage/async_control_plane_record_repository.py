from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite

from orket.core.contracts.control_plane_effect_journal_models import (
    CheckpointAcceptanceRecord,
    EffectJournalEntryRecord,
)
from orket.core.contracts.control_plane_models import (
    FinalTruthRecord,
    LeaseRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository


class ControlPlaneRecordConflictError(ValueError):
    """Raised when a control-plane record id is reused with different content."""


class AsyncControlPlaneRecordRepository(ControlPlaneRecordRepository):
    """Durable SQLite repository for append-only ControlPlane records."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
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

    async def _execute(self, operation, *, row_factory: bool = False, commit: bool = False):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                if row_factory:
                    conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
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
        insert_op,
        parse_existing,
    ):
        async def _op(conn: aiosqlite.Connection):
            cursor = await conn.execute(f"SELECT payload_json FROM {table} WHERE {id_field} = ?", (id_value,))
            existing = await cursor.fetchone()
            if existing is not None:
                existing_payload = str(existing["payload_json"] if isinstance(existing, aiosqlite.Row) else existing[0])
                if existing_payload != payload_json:
                    raise ControlPlaneRecordConflictError(f"{table}.{id_field} reused with different payload")
                return parse_existing(existing_payload)
            return await insert_op(conn)

        return await self._execute(_op, row_factory=True, commit=True)

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
