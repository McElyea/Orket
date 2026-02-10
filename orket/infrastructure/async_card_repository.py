"""
Async Card Repository - The Reconstruction (V2)

Hardened for parallel execution with safe locking patterns.
"""
from __future__ import annotations
import aiosqlite
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

from orket.repositories import CardRepository
from orket.schema import CardStatus, CardType
from orket.domain.records import IssueRecord, CardRecord


class AsyncCardRepository(CardRepository):
    """
    Async implementation of CardRepository using aiosqlite.
    Hardened for concurrent write operations.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        """Ensure database schema exists. Assumes already locked or inside a transaction."""
        if self._initialized:
            return

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
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                verification_json TEXT,
                metrics_json TEXT,
                depends_on_json TEXT,
                created_at DATETIME
            )
        """)
        
        # Migration
        try:
            await conn.execute("ALTER TABLE issues ADD COLUMN depends_on_json TEXT")
        except aiosqlite.OperationalError:
            pass

        try:
            await conn.execute("ALTER TABLE issues ADD COLUMN retry_count INTEGER DEFAULT 0")
            await conn.execute("ALTER TABLE issues ADD COLUMN max_retries INTEGER DEFAULT 3")
        except aiosqlite.OperationalError:
            pass

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
        self._initialized = True

    async def get_by_id(self, card_id: str) -> Optional[IssueRecord]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,))
                row = await cursor.fetchone()
                if not row: return None
                return IssueRecord.model_validate(self._deserialize_row(dict(row)))

    async def get_by_build(self, build_id: str) -> List[IssueRecord]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC", (build_id,))
                rows = await cursor.fetchall()
                return [IssueRecord.model_validate(self._deserialize_row(dict(row))) for row in rows]

    async def save(self, record: IssueRecord | Dict[str, Any]) -> None:
        if isinstance(record, dict):
            record = IssueRecord.model_validate(record)

        summary = record.summary or "Unnamed Unit"
        v_json = json.dumps(record.verification)
        m_json = json.dumps(record.metrics)
        d_json = json.dumps(record.depends_on)

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    """INSERT OR REPLACE INTO issues
                       (id, session_id, build_id, seat, summary, type, priority, sprint,
                        status, note, retry_count, max_retries, verification_json, metrics_json, depends_on_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (record.id, record.session_id, record.build_id, record.seat, summary,
                     record.type.value if hasattr(record.type, "value") else str(record.type),
                     record.priority, record.sprint,
                     record.status.value if hasattr(record.status, "value") else str(record.status),
                     record.note, record.retry_count, record.max_retries, v_json, m_json, d_json, record.created_at or datetime.now(UTC).isoformat())
                )
                await conn.commit()

    async def update_status(self, card_id: str, status: CardStatus, assignee: Optional[str] = None) -> None:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                if assignee:
                    await conn.execute("UPDATE issues SET status = ?, assignee = ? WHERE id = ?", (status.value, assignee, card_id))
                else:
                    await conn.execute("UPDATE issues SET status = ? WHERE id = ?", (status.value, card_id))
                
                # Internal transaction addition (bypass lock)
                await conn.execute("INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                                 (card_id, assignee or "system", f"Set Status to '{status.value}'"))
                await conn.commit()

    async def add_transaction(self, card_id: str, role: str, action: str) -> None:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute("INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)", (card_id, role, action))
                await conn.commit()

    async def get_card_history(self, card_id: str) -> List[str]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM card_transactions WHERE card_id = ? ORDER BY timestamp ASC", (card_id,))
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    ts = datetime.fromisoformat(row['timestamp'].replace(' ', 'T'))
                    history.append(f"{ts.strftime('%m/%d/%Y %I:%M%p')}: {row['role']} -> {row['action']}")
                return history

    async def reset_build(self, build_id: str) -> None:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute("UPDATE issues SET status = ? WHERE build_id = ?", (CardStatus.READY.value, build_id))
                await conn.commit()

    async def add_comment(self, issue_id: str, author: str, content: str) -> None:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute("INSERT INTO comments (issue_id, author, content, created_at) VALUES (?, ?, ?, ?)",
                                 (issue_id, author, content, datetime.now(UTC).isoformat()))
                await conn.commit()

    async def get_comments(self, issue_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at ASC", (issue_id,))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_independent_ready_issues(self, build_id: str) -> List[IssueRecord]:
        # Uses existing locked methods gracefully
        all_issues = await self.get_by_build(build_id)
        done_ids = {i.id for i in all_issues if i.status == CardStatus.DONE}
        ready_candidates = []
        for issue in all_issues:
            if issue.status == CardStatus.READY:
                if all(dep_id in done_ids for dep_id in issue.depends_on):
                    ready_candidates.append(issue)
        return ready_candidates

    def _deserialize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        for field in ['verification_json', 'metrics_json', 'depends_on_json']:
            target = field.replace('_json', '')
            if row.get(field):
                try: row[target] = json.loads(row[field])
                except json.JSONDecodeError: row[target] = [] if target == 'depends_on' else {}
            else:
                row[target] = [] if target == 'depends_on' else {}
        return row

