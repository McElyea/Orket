"""
Async SQLite Database for Webhook Event Tracking - The Reconstruction

Persists:
- PR review cycles (prevents in-memory loss on restart)
- Review failure reasons
- Webhook event history

Reconstructed to use aiosqlite for true async I/O.
"""
from __future__ import annotations
import aiosqlite
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC

from orket.logging import log_event


class WebhookDatabase:
    """
    Data Access Layer for webhook event persistence.
    Uses aiosqlite for non-blocking review cycle tracking.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        """
        if db_path is None:
            db_path = Path.cwd() / ".orket" / "webhook.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _ensure_initialized(self):
        """Ensure database schema exists."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as conn:
            # PR review cycles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pr_review_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_key TEXT UNIQUE NOT NULL,
                    repo_full_name TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    cycle_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(repo_full_name, pr_number)
                )
            """)

            # Review failure reasons table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS review_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pr_key TEXT NOT NULL,
                    cycle_number INTEGER NOT NULL,
                    reviewer TEXT,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pr_key) REFERENCES pr_review_cycles(pr_key)
                )
            """)

            # Webhook event log
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    pr_key TEXT,
                    payload TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Bug Fix Phases table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bug_fix_phases (
                    rock_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_pr_key ON pr_review_cycles(pr_key)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_repo_pr ON pr_review_cycles(repo_full_name, pr_number)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_failure_pr_key ON review_failures(pr_key)")

            await conn.commit()
            log_event("webhook_db", "Async database schema initialized", "info")

        self._initialized = True

    async def get_pr_cycle_count(self, repo_full_name: str, pr_number: int) -> int:
        """
        Get current review cycle count for a PR.
        """
        await self._ensure_initialized()
        pr_key = f"{repo_full_name}#{pr_number}"

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT cycle_count FROM pr_review_cycles WHERE pr_key = ?",
                (pr_key,)
            )
            row = await cursor.fetchone()
            return row["cycle_count"] if row else 0

    async def increment_pr_cycle(self, repo_full_name: str, pr_number: int) -> int:
        """
        Increment review cycle count for a PR.
        """
        await self._ensure_initialized()
        pr_key = f"{repo_full_name}#{pr_number}"

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Insert or update
            await conn.execute("""
                INSERT INTO pr_review_cycles (pr_key, repo_full_name, pr_number, cycle_count, updated_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(pr_key) DO UPDATE SET
                    cycle_count = cycle_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (pr_key, repo_full_name, pr_number))

            # Get new count
            cursor = await conn.execute("SELECT cycle_count FROM pr_review_cycles WHERE pr_key = ?", (pr_key,))
            row = await cursor.fetchone()
            await conn.commit()

            new_count = row["cycle_count"]
            log_event("webhook_db", f"Incremented PR cycle: {pr_key} -> {new_count}", "info")
            return new_count

    async def add_failure_reason(self, repo_full_name: str, pr_number: int, reviewer: str, reason: str):
        """
        Record a review failure reason.
        """
        await self._ensure_initialized()
        pr_key = f"{repo_full_name}#{pr_number}"
        cycle_count = await self.get_pr_cycle_count(repo_full_name, pr_number)

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO review_failures (pr_key, cycle_number, reviewer, reason)
                VALUES (?, ?, ?, ?)
            """, (pr_key, cycle_count, reviewer, reason))
            await conn.commit()
            log_event("webhook_db", f"Recorded failure reason for {pr_key}", "info")

    async def get_failure_reasons(self, repo_full_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all failure reasons for a PR.
        """
        await self._ensure_initialized()
        pr_key = f"{repo_full_name}#{pr_number}"

        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT cycle_number, reviewer, reason, created_at
                FROM review_failures
                WHERE pr_key = ?
                ORDER BY cycle_number ASC
            """, (pr_key,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def save_bug_fix_phase(self, phase: Any):
        """Save a bug fix phase to the database."""
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO bug_fix_phases (rock_id, data_json, status, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (phase.rock_id, phase.model_dump_json(), phase.status.value))
            await conn.commit()

    async def get_bug_fix_phase(self, rock_id: str) -> Optional[Any]:
        """Retrieve a bug fix phase from the database."""
        await self._ensure_initialized()
        from orket.domain.bug_fix_phase import BugFixPhase
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT data_json FROM bug_fix_phases WHERE rock_id = ?",
                (rock_id,)
            )
            row = await cursor.fetchone()
            if row:
                return BugFixPhase.model_validate_json(row["data_json"])
            return None

    async def close_pr_cycle(self, repo_full_name: str, pr_number: int, status: str = "closed"):
        """
        Mark a PR review cycle as closed.
        """
        await self._ensure_initialized()
        pr_key = f"{repo_full_name}#{pr_number}"

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE pr_review_cycles
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE pr_key = ?
            """, (status, pr_key))
            await conn.commit()
            log_event("webhook_db", f"Closed PR cycle: {pr_key} ({status})", "info")

    async def log_webhook_event(self, event_type: str, pr_key: Optional[str], payload: str, result: str):
        """
        Log a webhook event for debugging/auditing.
        """
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                INSERT INTO webhook_events (event_type, pr_key, payload, result)
                VALUES (?, ?, ?, ?)
            """, (event_type, pr_key, payload, result))
            await conn.commit()

    async def get_active_prs(self) -> List[Dict[str, Any]]:
        """
        Get all active PR review cycles.
        """
        await self._ensure_initialized()
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT pr_key, repo_full_name, pr_number, cycle_count, created_at, updated_at
                FROM pr_review_cycles
                WHERE status = 'active'
                ORDER BY updated_at DESC
            """)

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]