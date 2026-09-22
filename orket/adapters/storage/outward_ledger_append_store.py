from __future__ import annotations

import json
from dataclasses import replace

import aiosqlite

from orket.adapters.storage.sqlite_migrations import SQLiteMigration
from orket.core.domain.outward_ledger import event_hash_for
from orket.core.domain.outward_ledger_integrity import (
    ANCHOR_SCHEMA,
    LedgerAnchor,
    OutwardLedgerIntegrityError,
    append_chain_hash,
)
from orket.core.domain.outward_run_events import LedgerEvent, validate_ledger_event

LEDGER_APPEND_MIGRATION = SQLiteMigration(
    version=2, name="outward_ledger_append_commitments_v2",
    statements=(
        """CREATE TABLE outward_ledger_heads_v2 (
            run_id TEXT PRIMARY KEY, event_count INTEGER NOT NULL CHECK(event_count >= 0),
            chain_hash TEXT NOT NULL, origin_ref TEXT NOT NULL
        )""",
        """CREATE TABLE outward_ledger_commits_v2 (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
            append_sequence INTEGER NOT NULL CHECK(append_sequence > 0),
            event_hash TEXT NOT NULL, chain_hash TEXT NOT NULL,
            UNIQUE(run_id, append_sequence)
        )""",
        """CREATE TRIGGER outward_ledger_insert_v2 BEFORE INSERT ON run_events
        WHEN EXISTS (SELECT 1 FROM run_events WHERE event_id=NEW.event_id)
        OR NOT EXISTS (SELECT 1 FROM outward_ledger_commits_v2 c
            WHERE c.event_id=NEW.event_id AND c.run_id=NEW.run_id AND c.event_hash=NEW.event_hash)
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_LEDGER_COMMITMENT_REQUIRED'); END""",
        """CREATE TRIGGER outward_ledger_update_v2 BEFORE UPDATE ON run_events
        WHEN EXISTS (SELECT 1 FROM outward_ledger_commits_v2 WHERE event_id=OLD.event_id)
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_LEDGER_EVENT_IMMUTABLE'); END""",
        """CREATE TRIGGER outward_ledger_delete_v2 BEFORE DELETE ON run_events
        WHEN EXISTS (SELECT 1 FROM outward_ledger_commits_v2 WHERE event_id=OLD.event_id)
        BEGIN SELECT RAISE(ABORT, 'E_OUTWARD_LEDGER_EVENT_IMMUTABLE'); END""",
    ),
)


side_effecting = True


async def read_append_head(connection: aiosqlite.Connection, run_id: str) -> LedgerAnchor:
    cursor = await connection.execute(
        "SELECT event_count, chain_hash, origin_ref FROM outward_ledger_heads_v2 WHERE run_id=?", (run_id,),
    )
    row = await cursor.fetchone()
    anchor = LedgerAnchor.parse({
        "schema_version": ANCHOR_SCHEMA, "run_id": run_id,
        "event_count": row[0], "chain_hash": row[1], "origin_ref": row[2],
    }) if row is not None else LedgerAnchor(run_id)
    counts = await (await connection.execute(
        """SELECT (SELECT COUNT(*) FROM run_events WHERE run_id=?),
                  (SELECT COUNT(*) FROM outward_ledger_commits_v2 WHERE run_id=?)""", (run_id, run_id),
    )).fetchone()
    if row is None and (counts[0] or counts[1]):
        raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_UNSEALED: explicit legacy disposition required", category="unsealed")
    if counts[0] != anchor.event_count or counts[1] != anchor.event_count:
        raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_RETAINED_COUNT_MISMATCH")
    if anchor.event_count:
        tail = await (await connection.execute(
            "SELECT chain_hash FROM outward_ledger_commits_v2 WHERE run_id=? AND append_sequence=?",
            (run_id, anchor.event_count),
        )).fetchone()
        if tail is None or tail[0] != anchor.chain_hash:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_RETAINED_HEAD_MISMATCH")
    return anchor


class OutwardEventAppend:
    """An application-owned writer transaction; one implementation of append authority."""

    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection, head: LedgerAnchor) -> None:
        self._connection, self._head = connection, head

    @property
    def next_sequence(self) -> int:
        return self._head.event_count + 1

    async def append(self, event: LedgerEvent) -> LedgerEvent:
        validate_ledger_event(event)
        if event.run_id != self._head.run_id or not self._connection.in_transaction:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_APPEND_TRANSACTION_SCOPE")
        # Capture caller-owned nested data once at the serialized writer boundary.
        payload_json = json.dumps(event.payload, sort_keys=True, separators=(",", ":"))
        captured = replace(event, payload=json.loads(payload_json))
        digest = event_hash_for(captured)
        if event.event_hash not in (None, digest) or event.chain_hash is not None:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_CALLER_COMMITMENT_MISMATCH")
        stored = replace(captured, event_hash=digest)
        sequence = self.next_sequence
        chain = append_chain_hash(stored, sequence, self._head.chain_hash, self._head.origin_ref)
        await self._connection.execute(
            "INSERT INTO outward_ledger_commits_v2 VALUES (?, ?, ?, ?, ?)",
            (stored.event_id, stored.run_id, sequence, digest, chain),
        )
        await self._connection.execute(
            """INSERT INTO run_events (
                event_id, event_type, run_id, turn, agent_id, at, payload_json, event_hash, chain_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (stored.event_id, stored.event_type, stored.run_id, stored.turn, stored.agent_id, stored.at,
             payload_json, stored.event_hash, stored.chain_hash),
        )
        await self._connection.execute(
            """INSERT INTO outward_ledger_heads_v2 VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET event_count=excluded.event_count, chain_hash=excluded.chain_hash""",
            (stored.run_id, sequence, chain, self._head.origin_ref),
        )
        self._head = replace(self._head, event_count=sequence, chain_hash=chain)
        return stored
