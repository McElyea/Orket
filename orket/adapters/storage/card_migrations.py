from __future__ import annotations

import aiosqlite


class CardMigrations:
    """Database schema bootstrap and additive migrations for issue storage."""

    def __init__(self) -> None:
        self.initialized = False

    async def ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        if self.initialized:
            return

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

        try:
            await conn.execute("ALTER TABLE issues ADD COLUMN depends_on_json TEXT")
        except aiosqlite.OperationalError:
            pass

        try:
            await conn.execute("ALTER TABLE issues ADD COLUMN retry_count INTEGER DEFAULT 0")
            await conn.execute("ALTER TABLE issues ADD COLUMN max_retries INTEGER DEFAULT 3")
        except aiosqlite.OperationalError:
            pass

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
        self.initialized = True
