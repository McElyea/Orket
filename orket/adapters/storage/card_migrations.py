from __future__ import annotations

import contextlib

import aiosqlite

CARD_SCHEMA_USER_VERSION = 1


class CardMigrations:
    """Database schema bootstrap and additive migrations for issue storage."""

    async def ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute("PRAGMA journal_mode=WAL")
        version_cursor = await conn.execute("PRAGMA user_version")
        version_row = await version_cursor.fetchone()
        user_version = int(version_row[0] or 0) if version_row else 0

        await conn.execute(
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
                created_at DATETIME
            )
            """
        )

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN depends_on_json TEXT")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN retry_count INTEGER DEFAULT 0")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN max_retries INTEGER DEFAULT 3")

        with contextlib.suppress(aiosqlite.OperationalError):
            await conn.execute("ALTER TABLE issues ADD COLUMN params_json TEXT")

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id TEXT,
                author TEXT,
                content TEXT,
                created_at DATETIME,
                FOREIGN KEY(issue_id) REFERENCES issues(id)
            )
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS card_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT,
                role TEXT,
                action TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if user_version < CARD_SCHEMA_USER_VERSION:
            await conn.execute(f"PRAGMA user_version = {CARD_SCHEMA_USER_VERSION}")
        await conn.commit()
