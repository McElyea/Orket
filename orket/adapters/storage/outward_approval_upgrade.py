from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.outward_approval_migrations import OUTWARD_APPROVAL_MIGRATIONS
from orket.adapters.storage.sqlite_backup import prepare_sqlite_migration_copy
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner

side_effecting = True


async def migrate_outward_approval_copy(*, source: Path, backup: Path, destination: Path, writers_stopped: bool) -> dict:
    """Offline copy upgrade. The caller must stop old workers, including already authorized calls."""
    prepared = await prepare_sqlite_migration_copy(
        source=source, backup=backup, destination=destination, writers_stopped=writers_stopped,
    )
    source, backup, destination = prepared.source, prepared.backup, prepared.destination
    async with connect_sqlite_wal(destination) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await SQLiteMigrationRunner(namespace="outward_approvals").apply(conn, OUTWARD_APPROVAL_MIGRATIONS)
            cursor = await conn.execute("""SELECT status, COUNT(*) FROM outward_approval_proposals_v2
                WHERE authorization_json IS NULL GROUP BY status ORDER BY status""")
            legacy = {str(row[0]): int(row[1]) for row in await cursor.fetchall()}
            await conn.commit()
        finally:
            if conn.in_transaction:
                await conn.rollback()
    return {
        "source": str(source), "backup": str(backup), "destination": str(destination),
        "backup_sha256": prepared.backup_sha256,
        "schema_version": 2, "unbound_legacy_proposals_by_status": legacy,
        "legacy_dispatch_enabled": False, "old_writer_table_available": False,
    }
