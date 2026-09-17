from __future__ import annotations

from pathlib import Path

import aiosqlite

from orket.adapters.storage.outward_ledger_legacy_import import import_legacy_run, validate_legacy_inventory
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import _MIGRATIONS as EVENT_MIGRATIONS
from orket.adapters.storage.outward_run_store import _MIGRATIONS as RUN_MIGRATIONS
from orket.adapters.storage.sqlite_backup import prepare_sqlite_migration_copy
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.domain.outward_ledger_integrity import OutwardLedgerIntegrityError

side_effecting = True


async def migrate_outward_ledger_copy(
    *, source: Path, backup: Path, destination: Path, writers_stopped: bool, allow_unsealed: bool = False,
) -> dict:
    """Retain a SQLite snapshot, then validate and import only its new candidate copy."""
    prepared = await prepare_sqlite_migration_copy(
        source=source, backup=backup, destination=destination, writers_stopped=writers_stopped,
    )
    async with connect_sqlite_wal(prepared.destination) as connection:
        connection.row_factory = aiosqlite.Row
        await connection.execute("BEGIN IMMEDIATE")
        try:
            await validate_legacy_inventory(connection)
            await SQLiteMigrationRunner(namespace="outward_runs").apply(connection, RUN_MIGRATIONS)
            await SQLiteMigrationRunner(namespace="outward_run_events").apply(connection, EVENT_MIGRATIONS)
            runs = await _import_runs(connection, prepared.destination, prepared.backup_sha256, allow_unsealed)
            await connection.commit()
        finally:
            if connection.in_transaction:
                await connection.rollback()
    return {
        "schema_version": "outward_ledger_migration.v2",
        "source": str(prepared.source), "backup": str(prepared.backup), "destination": str(prepared.destination),
        "backup_sha256": prepared.backup_sha256, "runs": runs,
        "authenticity": "not_established", "execution_authority": "unchanged", "candidate_activated": False,
        "writers_stopped": "operator_acknowledged", "unsealed_import_allowed": allow_unsealed,
    }


async def _import_runs(connection, destination: Path, backup_sha256: str, allow_unsealed: bool) -> list[dict]:
    cursor = await connection.execute("SELECT run_id FROM outward_runs ORDER BY run_id")
    snapshots, reports = OutwardLedgerSnapshotStore(destination), []
    while rows := await cursor.fetchmany(1000):
        for row in rows:
            run_id = row[0]
            if not isinstance(run_id, str) or not run_id.strip():
                raise OutwardLedgerIntegrityError("E_OUTWARD_LEDGER_MIGRATION_RUN_IDENTITY")
            head = await (await connection.execute(
                "SELECT 1 FROM outward_ledger_heads_v2 WHERE run_id=?", (run_id,),
            )).fetchone()
            report = {"disposition": "retained_v2"} if head else await import_legacy_run(
                connection, run_id, origin_ref="legacy:" + backup_sha256, allow_unsealed=allow_unsealed,
            )
            snapshot = await snapshots.read_in_transaction(connection, run_id)
            reports.append({
                "run_id": run_id, **report, "event_count": snapshot.independent_count,
                "anchor": snapshot.anchor.to_dict(), "execution_generation": snapshot.run.execution_generation,
                "retained_integrity": "valid", "snapshot_completeness": "valid",
            })
    return reports
