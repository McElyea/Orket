from __future__ import annotations

import aiosqlite
import pytest

from orket.adapters.storage.sqlite_migrations import SQLiteMigration, SQLiteMigrationRunner


@pytest.mark.asyncio
async def test_sqlite_migration_runner_records_and_skips_applied_versions(tmp_path) -> None:
    """Layer: integration. Verifies SQLite migrations apply once and record durable migration truth."""
    db_path = tmp_path / "migrations.db"
    runner = SQLiteMigrationRunner(namespace="unit_test")
    migration = SQLiteMigration(
        version=1,
        name="create_example",
        statements=("CREATE TABLE example (id TEXT PRIMARY KEY)",),
    )

    async with aiosqlite.connect(db_path) as conn:
        await runner.apply(conn, [migration])
        await runner.apply(conn, [migration])
        await conn.commit()

        cursor = await conn.execute(
            "SELECT namespace, version, name FROM schema_migrations WHERE namespace = ?",
            ("unit_test",),
        )
        rows = await cursor.fetchall()

    assert rows == [("unit_test", 1, "create_example")]
