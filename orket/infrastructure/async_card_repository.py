"""
Async Card Repository - The Reconstruction

Replaces blocking sqlite3 with aiosqlite for true async I/O.

Key Changes from SQLiteCardRepository:
1. All methods are async
2. Uses aiosqlite instead of sqlite3
3. Proper async context managers
4. Type hints throughout
5. No bare except clauses
"""
from __future__ import annotations
import aiosqlite
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

from orket.repositories import CardRepository
from orket.schema import CardStatus


class AsyncCardRepository(CardRepository):
    """
    Async implementation of CardRepository using aiosqlite.

    All methods are truly async - no blocking I/O in event loop.
    """

    def __init__(self, db_path: str | Path):
        """
        Initialize repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = str(db_path)
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure database schema exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
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
                    verification_json TEXT,
                    metrics_json TEXT,
                    created_at DATETIME
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id TEXT,
                    author TEXT,
                    content TEXT,
                    created_at DATETIME,
                    FOREIGN KEY(issue_id) REFERENCES issues(id)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS card_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT,
                    role TEXT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await conn.commit()

        self._initialized = True

    async def get_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """
        Get card by ID.

        Args:
            card_id: Card ID to fetch

        Returns:
            Card data dict or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM issues WHERE id = ?",
                (card_id,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._deserialize_row(dict(row))

    async def get_by_build(self, build_id: str) -> List[Dict[str, Any]]:
        """
        Get all cards for a build.

        Args:
            build_id: Build ID

        Returns:
            List of card data dicts
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC",
                (build_id,)
            )
            rows = await cursor.fetchall()

            return [self._deserialize_row(dict(row)) for row in rows]

    async def save(self, card_data: Dict[str, Any]) -> None:
        """
        Save or update a card.

        Args:
            card_data: Card data to save
        """
        await self._ensure_initialized()

        summary = card_data.get('summary') or card_data.get('name') or "Unnamed Unit"
        v_json = json.dumps(card_data.get('verification', {}))
        m_json = json.dumps(card_data.get('metrics', {}))

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """INSERT OR REPLACE INTO issues
                   (id, session_id, build_id, seat, summary, type, priority, sprint,
                    status, note, verification_json, metrics_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    card_data['id'],
                    card_data.get('session_id'),
                    card_data.get('build_id'),
                    card_data['seat'],
                    summary,
                    card_data['type'],
                    card_data['priority'],
                    card_data.get('sprint'),
                    card_data['status'],
                    card_data.get('note'),
                    v_json,
                    m_json,
                    datetime.now(UTC).isoformat()
                )
            )
            await conn.commit()

    async def update_status(
        self,
        card_id: str,
        status: CardStatus,
        assignee: Optional[str] = None
    ) -> None:
        """
        Update card status.

        Args:
            card_id: Card ID
            status: New status
            assignee: Optional assignee
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            if assignee:
                await conn.execute(
                    "UPDATE issues SET status = ?, assignee = ? WHERE id = ?",
                    (status.value, assignee, card_id)
                )
            else:
                await conn.execute(
                    "UPDATE issues SET status = ? WHERE id = ?",
                    (status.value, card_id)
                )
            await conn.commit()

        await self.add_transaction(
            card_id,
            assignee or "system",
            f"Set Status to '{status.value}'"
        )

    async def add_transaction(
        self,
        card_id: str,
        role: str,
        action: str
    ) -> None:
        """
        Add audit transaction.

        Args:
            card_id: Card ID
            role: Role making the change
            action: Action description
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, role, action)
            )
            await conn.commit()

    async def get_card_history(self, card_id: str) -> List[str]:
        """
        Get card transaction history.

        Args:
            card_id: Card ID

        Returns:
            List of transaction strings
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM card_transactions WHERE card_id = ? ORDER BY timestamp ASC",
                (card_id,)
            )
            rows = await cursor.fetchall()

            history = []
            for row in rows:
                ts_str = row['timestamp']
                # Parse and format timestamp
                ts = datetime.fromisoformat(ts_str.replace(' ', 'T'))
                formatted = ts.strftime("%m/%d/%Y %I:%M%p")
                history.append(f"{formatted}: {row['role']} -> {row['action']}")

            return history

    async def reset_build(self, build_id: str) -> None:
        """
        Reset all cards in a build to READY status.

        Args:
            build_id: Build ID
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE issues SET status = ? WHERE build_id = ?",
                (CardStatus.READY.value, build_id)
            )
            await conn.commit()

    def _deserialize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deserialize database row into card data.

        Args:
            row: Raw database row

        Returns:
            Card data with JSON fields deserialized
        """
        if row.get('verification_json'):
            try:
                row['verification'] = json.loads(row['verification_json'])
            except json.JSONDecodeError:
                row['verification'] = {}

        if row.get('metrics_json'):
            try:
                row['metrics'] = json.loads(row['metrics_json'])
            except json.JSONDecodeError:
                row['metrics'] = {}

        return row


# Compatibility: Allow sync-style usage for gradual migration
class CardRepositoryAdapter(CardRepository):
    """
    Adapter that wraps AsyncCardRepository for sync code.

    Use this during migration period only. New code should use
    AsyncCardRepository directly.
    """

    def __init__(self, async_repo: AsyncCardRepository):
        import asyncio
        self._async_repo = async_repo
        self._loop = asyncio.get_event_loop()

    def get_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper for get_by_id."""
        return self._loop.run_until_complete(
            self._async_repo.get_by_id(card_id)
        )

    def get_by_build(self, build_id: str) -> List[Dict[str, Any]]:
        """Sync wrapper for get_by_build."""
        return self._loop.run_until_complete(
            self._async_repo.get_by_build(build_id)
        )

    def save(self, card_data: Dict[str, Any]) -> None:
        """Sync wrapper for save."""
        self._loop.run_until_complete(
            self._async_repo.save(card_data)
        )

    def update_status(
        self,
        card_id: str,
        status: CardStatus,
        assignee: Optional[str] = None
    ) -> None:
        """Sync wrapper for update_status."""
        self._loop.run_until_complete(
            self._async_repo.update_status(card_id, status, assignee)
        )
