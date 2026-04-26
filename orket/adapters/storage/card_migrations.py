from __future__ import annotations

import contextlib

import aiosqlite

from .sqlite_migrations import SQLiteMigration, SQLiteMigrationRunner

CARD_SCHEMA_USER_VERSION = 1

CARD_BOOTSTRAP_MIGRATIONS = [
    SQLiteMigration(
        version=1,
        name="card_repository_bootstrap",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                build_id TEXT,
                seat TEXT,
                summary TEXT,
                type TEXT,
                priority TEXT,
                sprint TEXT,
                status TEXT DEFAULT 'ready',
                assignee TEXT,
                note TEXT,
                resolution TEXT,
                credits_spent REAL DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                verification_json TEXT,
                metrics_json TEXT,
                depends_on_json TEXT,
                params_json TEXT,
                created_at DATETIME
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id TEXT,
                author TEXT,
                content TEXT,
                created_at DATETIME,
                FOREIGN KEY(issue_id) REFERENCES issues(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS card_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT,
                role TEXT,
                action TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ),
    )
]


class CardMigrations:
    """Database schema bootstrap and additive migrations for issue storage."""

    def __init__(self) -> None:
        self._runner = SQLiteMigrationRunner(namespace="card_repository")

    async def ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL")
        version_cursor = await conn.execute("PRAGMA user_version")
        version_row = await version_cursor.fetchone()
        user_version = int(version_row[0] or 0) if version_row else 0

        await self._runner.apply(conn, CARD_BOOTSTRAP_MIGRATIONS)

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN depends_on_json TEXT")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN retry_count INTEGER DEFAULT 0")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN max_retries INTEGER DEFAULT 3")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN params_json TEXT")

        if user_version < CARD_SCHEMA_USER_VERSION:
            await conn.execute(f"PRAGMA user_version = {CARD_SCHEMA_USER_VERSION}")
        await conn.commit()
