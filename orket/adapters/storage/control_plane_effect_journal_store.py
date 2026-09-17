from __future__ import annotations

import aiosqlite

from orket.core.contracts.control_plane_effect_journal_models import EffectJournalEntryRecord

side_effecting = True


async def ensure_effect_journal_schema(conn: aiosqlite.Connection) -> None:
    await conn.execute("""CREATE TABLE IF NOT EXISTS effect_journal_entries (
        journal_entry_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, publication_sequence INTEGER NOT NULL,
        entry_digest TEXT NOT NULL, payload_json TEXT NOT NULL
    )""")
    await conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_effect_journal_run_sequence
        ON effect_journal_entries (run_id, publication_sequence)""")


async def insert_effect_journal_entry(
    conn: aiosqlite.Connection, *, run_id: str, entry: EffectJournalEntryRecord,
) -> EffectJournalEntryRecord:
    await conn.execute("""INSERT INTO effect_journal_entries (
        journal_entry_id, run_id, publication_sequence, entry_digest, payload_json
    ) VALUES (?, ?, ?, ?, ?)""", (
        entry.journal_entry_id, run_id, entry.publication_sequence, entry.entry_digest, entry.model_dump_json(),
    ))
    return entry


async def list_effect_journal_entries(conn: aiosqlite.Connection, *, run_id: str) -> list[EffectJournalEntryRecord]:
    cursor = await conn.execute("""SELECT payload_json FROM effect_journal_entries
        WHERE run_id = ? ORDER BY publication_sequence ASC""", (run_id,))
    return [EffectJournalEntryRecord.model_validate_json(str(row[0])) for row in await cursor.fetchall()]
