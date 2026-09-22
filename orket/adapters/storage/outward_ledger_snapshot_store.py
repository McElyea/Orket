from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from orket.adapters.storage.outward_ledger_append_store import read_append_head
from orket.adapters.storage.outward_run_event_store import event_from_row
from orket.adapters.storage.outward_run_store import run_record_from_row
from orket.core.domain.outward_ledger import (
    GENESIS_CHAIN_HASH,
    MAX_LEDGER_EXPORT_EVENTS,
    MAX_LEDGER_PAYLOAD_BYTES,
    event_hash_for,
)
from orket.core.domain.outward_ledger_integrity import (
    LedgerAnchor,
    OutwardLedgerIntegrityError,
    RetainedLedgerSnapshot,
    append_chain_hash,
)
from orket.core.domain.outward_run_events import LedgerEvent, validate_ledger_event

side_effecting = False


class OutwardLedgerSnapshotStore:
    side_effecting = False

    def __init__(self, db_path: str | Path, *, page_size: int = 1000,
                 connection: aiosqlite.Connection | None = None) -> None:
        if not 1 <= page_size <= 5000:
            raise ValueError("page_size must be between 1 and 5000")
        self.db_path, self.page_size = Path(db_path), page_size
        self.connection = connection

    async def read(self, run_id: str) -> RetainedLedgerSnapshot:
        if self.connection is not None:
            return await self.read_in_transaction(self.connection, run_id)
        uri = await asyncio.to_thread(lambda: self.db_path.resolve().as_uri() + "?mode=ro")
        try:
            async with aiosqlite.connect(uri, uri=True, timeout=5.0) as connection:
                connection.row_factory = aiosqlite.Row
                await connection.execute("PRAGMA query_only=ON")
                await connection.execute("BEGIN")
                return await self.read_in_transaction(connection, run_id)
        except OutwardLedgerIntegrityError:
            raise
        except (aiosqlite.DatabaseError, OSError) as exc:
            raise OutwardLedgerIntegrityError(
                f"E_OUTWARD_LEDGER_STORAGE_READ: {exc}", category="storage",
            ) from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise OutwardLedgerIntegrityError(f"E_OUTWARD_LEDGER_RECORD_INVALID: {exc}") from exc

    async def read_in_transaction(self, connection: aiosqlite.Connection, run_id: str) -> RetainedLedgerSnapshot:
        if not connection.in_transaction:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_TRANSACTION_REQUIRED")
        connection.row_factory = aiosqlite.Row
        row = await (await connection.execute("SELECT * FROM outward_runs WHERE run_id=?", (run_id,))).fetchone()
        if row is None:
            raise OutwardLedgerIntegrityError(f"Run '{run_id}' not found", category="not_found")
        tables = await (await connection.execute(
            """SELECT COUNT(*) FROM sqlite_master WHERE type='table'
            AND name IN ('outward_ledger_heads_v2', 'outward_ledger_commits_v2')""",
        )).fetchone()
        if tables[0] != 2:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_UNSEALED: v2 storage absent", category="unsealed")
        head = await read_append_head(connection, run_id)
        counts = await (await connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(payload_json AS BLOB))), 0) FROM run_events WHERE run_id=?",
            (run_id,),
        )).fetchone()
        # Bound the in-memory v1 projection; never return a prefix marked complete.
        if counts[0] > MAX_LEDGER_EXPORT_EVENTS or counts[1] > MAX_LEDGER_PAYLOAD_BYTES:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_RESOURCE_LIMIT", category="resource")
        events, chains = await self._read_pages(connection, head)
        if len(events) != counts[0] or len(events) != head.event_count:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_COUNT_MISMATCH")
        if (chains[-1] if chains else GENESIS_CHAIN_HASH) != head.chain_hash:
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_HEAD_MISMATCH")
        return RetainedLedgerSnapshot(run_record_from_row(row), tuple(events), head, counts[0], tuple(chains))

    async def _read_pages(
        self, connection: aiosqlite.Connection, head: LedgerAnchor,
    ) -> tuple[list[LedgerEvent], list[str]]:
        events: list[LedgerEvent] = []
        chains: list[str] = []
        previous = GENESIS_CHAIN_HASH
        while rows := await self._read_page(connection, head.run_id, len(events)):
            for row in rows:
                sequence = len(events) + 1
                if row["append_sequence"] != sequence or row["event_id"] is None:
                    raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_APPEND_SEQUENCE_MISMATCH")
                event = event_from_row(row)
                validate_ledger_event(event)
                if event.run_id != head.run_id or event_hash_for(event) != row["committed_event_hash"]:
                    raise OutwardLedgerIntegrityError(f"E_OUTWARD_LEDGER_EVENT_HASH_MISMATCH: sequence {sequence}")
                chain = append_chain_hash(event, sequence, previous, head.origin_ref)
                if chain != row["committed_chain_hash"]:
                    raise OutwardLedgerIntegrityError(f"E_OUTWARD_LEDGER_APPEND_HASH_MISMATCH: sequence {sequence}")
                events.append(event)
                chains.append(chain)
                previous = chain
                if len(events) > head.event_count:
                    raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_COUNT_MISMATCH")
        return events, chains

    async def _read_page(self, connection: aiosqlite.Connection, run_id: str, after: int):
        cursor = await connection.execute(
            """SELECT e.*, c.append_sequence, c.event_hash AS committed_event_hash,
                      c.chain_hash AS committed_chain_hash
            FROM outward_ledger_commits_v2 c LEFT JOIN run_events e ON e.event_id=c.event_id
            WHERE c.run_id=? AND c.append_sequence>? ORDER BY c.append_sequence LIMIT ?""",
            (run_id, after, self.page_size),
        )
        return await cursor.fetchall()
