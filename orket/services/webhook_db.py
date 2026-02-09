"""
SQLite Database for Webhook Event Tracking

Persists:
- PR review cycles (prevents in-memory loss on restart)
- Review failure reasons
- Webhook event history
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager

from orket.logging import log_event


class WebhookDatabase:
    """
    Data Access Layer for webhook event persistence.
    Uses SQLite for review cycle tracking and event history.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file (default: .orket/webhook.db)
        """
        if db_path is None:
            db_path = Path.cwd() / ".orket" / "webhook.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_schema(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # PR review cycles table
            cursor.execute("""
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
            cursor.execute("""
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    pr_key TEXT,
                    payload TEXT,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pr_key ON pr_review_cycles(pr_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_repo_pr ON pr_review_cycles(repo_full_name, pr_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_failure_pr_key ON review_failures(pr_key)")

            log_event("webhook_db", "Database schema initialized", "info")

    def get_pr_cycle_count(self, repo_full_name: str, pr_number: int) -> int:
        """
        Get current review cycle count for a PR.

        Args:
            repo_full_name: Repository full name (e.g., "orket/test-project")
            pr_number: PR number

        Returns:
            Current cycle count (0 if PR not found)
        """
        pr_key = f"{repo_full_name}#{pr_number}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT cycle_count FROM pr_review_cycles WHERE pr_key = ?",
                (pr_key,)
            )
            row = cursor.fetchone()
            return row["cycle_count"] if row else 0

    def increment_pr_cycle(self, repo_full_name: str, pr_number: int) -> int:
        """
        Increment review cycle count for a PR.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number

        Returns:
            New cycle count
        """
        pr_key = f"{repo_full_name}#{pr_number}"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert or update
            cursor.execute("""
                INSERT INTO pr_review_cycles (pr_key, repo_full_name, pr_number, cycle_count, updated_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(pr_key) DO UPDATE SET
                    cycle_count = cycle_count + 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (pr_key, repo_full_name, pr_number))

            # Get new count
            cursor.execute("SELECT cycle_count FROM pr_review_cycles WHERE pr_key = ?", (pr_key,))
            row = cursor.fetchone()

            new_count = row["cycle_count"]
            log_event("webhook_db", f"Incremented PR cycle: {pr_key} -> {new_count}", "info")
            return new_count

    def add_failure_reason(self, repo_full_name: str, pr_number: int, reviewer: str, reason: str):
        """
        Record a review failure reason.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number
            reviewer: Reviewer username
            reason: Failure reason/comment
        """
        pr_key = f"{repo_full_name}#{pr_number}"
        cycle_count = self.get_pr_cycle_count(repo_full_name, pr_number)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO review_failures (pr_key, cycle_number, reviewer, reason)
                VALUES (?, ?, ?, ?)
            """, (pr_key, cycle_count, reviewer, reason))

            log_event("webhook_db", f"Recorded failure reason for {pr_key}", "info")

    def get_failure_reasons(self, repo_full_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get all failure reasons for a PR.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number

        Returns:
            List of failure reason dicts
        """
        pr_key = f"{repo_full_name}#{pr_number}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cycle_number, reviewer, reason, created_at
                FROM review_failures
                WHERE pr_key = ?
                ORDER BY cycle_number ASC
            """, (pr_key,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def close_pr_cycle(self, repo_full_name: str, pr_number: int, status: str = "closed"):
        """
        Mark a PR review cycle as closed.

        Args:
            repo_full_name: Repository full name
            pr_number: PR number
            status: Final status (closed, merged, rejected)
        """
        pr_key = f"{repo_full_name}#{pr_number}"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE pr_review_cycles
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE pr_key = ?
            """, (status, pr_key))

            log_event("webhook_db", f"Closed PR cycle: {pr_key} ({status})", "info")

    def log_webhook_event(self, event_type: str, pr_key: Optional[str], payload: str, result: str):
        """
        Log a webhook event for debugging/auditing.

        Args:
            event_type: Type of webhook event
            pr_key: PR key (if applicable)
            payload: JSON payload (as string)
            result: Result of handling (success/error)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO webhook_events (event_type, pr_key, payload, result)
                VALUES (?, ?, ?, ?)
            """, (event_type, pr_key, payload, result))

    def get_active_prs(self) -> List[Dict[str, Any]]:
        """
        Get all active PR review cycles.

        Returns:
            List of active PR dicts
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pr_key, repo_full_name, pr_number, cycle_count, created_at, updated_at
                FROM pr_review_cycles
                WHERE status = 'active'
                ORDER BY updated_at DESC
            """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
