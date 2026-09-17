from __future__ import annotations

import aiosqlite

from orket.adapters.storage.outward_run_event_store import _MIGRATIONS as EVENT_MIGRATIONS
from orket.adapters.storage.outward_run_event_store import event_from_row
from orket.adapters.storage.outward_run_store import _MIGRATIONS as RUN_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.domain.outward_ledger import (
    GENESIS_CHAIN_HASH,
    MAX_LEDGER_EXPORT_EVENTS,
    MAX_LEDGER_PAYLOAD_BYTES,
    chain_hash_for,
    event_hash_for,
)
from orket.core.domain.outward_ledger_integrity import OutwardLedgerIntegrityError, append_chain_hash
from orket.core.domain.outward_run_events import validate_ledger_event

side_effecting = True


async def validate_legacy_inventory(connection: aiosqlite.Connection) -> None:
    """Reject unsupported schemas/partial v2 state before creating any new authority."""
    async with aiosqlite.connect(":memory:") as expected:
        for namespace, migrations in (("outward_runs", RUN_MIGRATIONS), ("outward_run_events", EVENT_MIGRATIONS)):
            versions = await (await connection.execute(
                "SELECT version, name FROM schema_migrations WHERE namespace=? ORDER BY version", (namespace,),
            )).fetchall()
            selected = migrations[:len(versions)]
            if not versions or [tuple(row) for row in versions] != [(m.version, m.name) for m in selected]:
                raise OutwardLedgerIntegrityError(f"E_OUTWARD_LEDGER_MIGRATION_SCHEMA: {namespace}")
            await SQLiteMigrationRunner(namespace=namespace).apply(expected, selected)
        if await _schema(connection) != await _schema(expected):
            raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_MIGRATION_SCHEMA: tables, indexes or writer guards differ")
    orphan = await (await connection.execute(
        "SELECT 1 FROM run_events e LEFT JOIN outward_runs r ON r.run_id=e.run_id WHERE r.run_id IS NULL LIMIT 1",
    )).fetchone()
    if orphan:
        raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_MIGRATION_ORPHAN_EVENT")
    if len(versions) == 2:
        await _validate_v2_inventory(connection)


async def _schema(connection: aiosqlite.Connection) -> list[tuple]:
    rows = await (await connection.execute(
        """SELECT type, name, tbl_name, sql FROM sqlite_master WHERE tbl_name IN (
            'outward_runs', 'run_events', 'outward_ledger_heads_v2', 'outward_ledger_commits_v2'
        ) ORDER BY type, name""",
    )).fetchall()
    return [(row[0], row[1], row[2], " ".join(row[3].split()) if row[3] else None) for row in rows]


async def _validate_v2_inventory(connection: aiosqlite.Connection) -> None:
    orphan = await (await connection.execute(
        """SELECT 1 FROM outward_ledger_heads_v2 h LEFT JOIN outward_runs r ON r.run_id=h.run_id
        WHERE r.run_id IS NULL UNION ALL
        SELECT 1 FROM outward_ledger_commits_v2 c
        LEFT JOIN outward_ledger_heads_v2 h ON h.run_id=c.run_id
        LEFT JOIN run_events e ON e.event_id=c.event_id AND e.run_id=c.run_id
        WHERE h.run_id IS NULL OR e.event_id IS NULL LIMIT 1""",
    )).fetchone()
    if orphan:
        raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_MIGRATION_ORPHAN_COMMITMENT")


async def import_legacy_run(connection, run_id: str, *, origin_ref: str, allow_unsealed: bool) -> dict:
    counts = await (await connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(payload_json AS BLOB))), 0) FROM run_events WHERE run_id=?",
        (run_id,),
    )).fetchone()
    if counts[0] > MAX_LEDGER_EXPORT_EVENTS or counts[1] > MAX_LEDGER_PAYLOAD_BYTES:
        raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_SNAPSHOT_RESOURCE_LIMIT", category="resource")
    cursor = await connection.execute(
        "SELECT * FROM run_events WHERE run_id=? ORDER BY run_id, turn, at, event_id", (run_id,),
    )
    sequence, unsealed, checked = 0, 0, 0
    v1_chain = append_chain = GENESIS_CHAIN_HASH
    while rows := await cursor.fetchmany(1000):
        commitments = []
        for row in rows:
            event = event_from_row(row)
            validate_ledger_event(event)
            digest = event_hash_for(event)
            v1_chain = chain_hash_for(v1_chain, digest)
            for actual, required in ((event.event_hash, digest), (event.chain_hash, v1_chain)):
                if actual is not None and actual != required:
                    raise OutwardLedgerIntegrityError(f"E_OUTWARD_LEDGER_LEGACY_HASH_MISMATCH: {event.event_id}")
                checked += actual is not None
            unsealed += event.event_hash is None or event.chain_hash is None
            if unsealed and not allow_unsealed:
                raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_UNSEALED_IMPORT_ACK_REQUIRED", category="unsealed")
            sequence += 1
            append_chain = append_chain_hash(event, sequence, append_chain, origin_ref)
            commitments.append((event.event_id, event.run_id, sequence, digest, append_chain))
        await connection.executemany("INSERT INTO outward_ledger_commits_v2 VALUES (?, ?, ?, ?, ?)", commitments)
    await connection.execute(
        "INSERT INTO outward_ledger_heads_v2 VALUES (?, ?, ?, ?)", (run_id, sequence, append_chain, origin_ref),
    )
    return {
        "disposition": "imported_legacy", "unsealed_events": unsealed, "available_hashes_checked": checked,
        "derived_v1_chain_hash": v1_chain,
    }
