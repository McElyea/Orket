from __future__ import annotations

from dataclasses import asdict

import aiosqlite

from orket.adapters.storage.control_plane_effect_journal_store import (
    ensure_effect_journal_schema,
    insert_effect_journal_entry,
    list_effect_journal_entries,
)
from orket.adapters.storage.control_plane_operator_action_support import (
    ensure_operator_action_schema,
)
from orket.adapters.storage.control_plane_recovery_store import (
    ensure_recovery_decision_schema,
)
from orket.adapters.storage.outward_effect_migrations import OUTWARD_EFFECT_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.contracts.control_plane_effect_journal_models import EffectJournalEntryRecord
from orket.core.domain.outward_effects import OutwardEffectRecord

side_effecting = True


async def ensure_outward_effect_schema(conn: aiosqlite.Connection) -> None:
    await ensure_effect_journal_schema(conn)
    await SQLiteMigrationRunner(namespace="outward_effects").apply(conn, OUTWARD_EFFECT_MIGRATIONS)
    await ensure_recovery_decision_schema(conn)
    await ensure_operator_action_schema(conn)


class OutwardEffectTransactionStore:
    """Effect and shared journal operations on an explicitly owned SQLite transaction."""

    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def get(self, effect_id: str) -> OutwardEffectRecord | None:
        cursor = await self.connection.execute("SELECT * FROM outward_effects WHERE effect_id = ?", (effect_id,))
        row = await cursor.fetchone()
        return OutwardEffectRecord(**dict(zip([column[0] for column in cursor.description], row, strict=True))) if row else None

    async def create(self, effect: OutwardEffectRecord) -> None:
        values = asdict(effect)
        await self.connection.execute(
            f"INSERT INTO outward_effects ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )

    async def transition(self, effect: OutwardEffectRecord, *, expected_state: str) -> None:
        cursor = await self.connection.execute("""UPDATE outward_effects
            SET state = ?, journal_entry_id = ?, dispatched_at = ?, receipt_json = ?, receipt_digest = ?, published_at = ?
            WHERE effect_id = ? AND owner_id = ? AND fencing_generation = ? AND state = ?""", (
            effect.state, effect.journal_entry_id, effect.dispatched_at, effect.receipt_json, effect.receipt_digest,
            effect.published_at, effect.effect_id, effect.owner_id, effect.fencing_generation, expected_state,
        ))
        if cursor.rowcount != 1:
            raise RuntimeError("E_OUTWARD_EFFECT_FENCE_CONFLICT")

    async def replace_claim_owner(self, previous: OutwardEffectRecord, replacement: OutwardEffectRecord) -> None:
        cursor = await self.connection.execute("""UPDATE outward_effects
            SET owner_id = ?, fencing_generation = ?, journal_entry_id = ?, recovery_decision_id = ?
            WHERE effect_id = ? AND state = 'claimed' AND dispatched_at IS NULL
              AND owner_id = ? AND fencing_generation = ? AND journal_entry_id = ?""", (
            replacement.owner_id, replacement.fencing_generation, replacement.journal_entry_id, replacement.recovery_decision_id,
            previous.effect_id, previous.owner_id, previous.fencing_generation, previous.journal_entry_id,
        ))
        if cursor.rowcount != 1:
            raise RuntimeError("E_OUTWARD_EFFECT_FENCE_CONFLICT")

    async def list_journal(self, run_id: str) -> list[EffectJournalEntryRecord]:
        return await list_effect_journal_entries(self.connection, run_id=run_id)

    async def append_journal(self, entry: EffectJournalEntryRecord) -> None:
        await insert_effect_journal_entry(self.connection, run_id=entry.run_id, entry=entry)
