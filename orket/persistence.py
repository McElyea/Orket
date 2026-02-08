import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class PersistenceManager:
    def __init__(self, db_path: str = "orket_persistence.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    name TEXT,
                    department TEXT,
                    status TEXT,
                    task_input TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    credits_total REAL DEFAULT 0,
                    transcript TEXT
                )
            """)
            conn.execute("""
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
                    created_at DATETIME,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_id TEXT,
                    author TEXT,
                    content TEXT,
                    created_at DATETIME,
                    FOREIGN KEY(issue_id) REFERENCES issues(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_snapshots (
                    session_id TEXT PRIMARY KEY,
                    config_json TEXT,
                    log_history TEXT,
                    captured_at DATETIME
                )
            """)
            conn.commit()

    def record_snapshot(self, session_id: str, config: Dict[str, Any], logs: List[Dict[str, Any]]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO session_snapshots (session_id, config_json, log_history, captured_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, json.dumps(config), json.dumps(logs), datetime.now().isoformat()))
            conn.commit()

    def get_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def start_session(self, session_id: str, run_type: str, name: str, department: str, task: str):      
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, type, name, department, status, task_input, start_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, run_type, name, department, "Started", task, datetime.now().isoformat())
            )
            conn.commit()

    def update_session_status(self, session_id: str, status: str, credits: float = 0, transcript: List[Dict[str, Any]] = None):
        with sqlite3.connect(self.db_path) as conn:
            t_json = json.dumps(transcript) if transcript else None
            conn.execute(
                "UPDATE sessions SET status = ?, credits_total = credits_total + ?, transcript = ?, end_time = ? WHERE id = ?",
                (status, credits, t_json, datetime.now().isoformat(), session_id)
            )
            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def add_issue(self, session_id: str, seat: str, summary: str, i_type: str, priority: str, sprint: str, note: str, build_id: str = None, issue_id_override: str = None):
        issue_id = issue_id_override or f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO issues (id, session_id, build_id, seat, summary, type, priority, sprint, status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (issue_id, session_id, build_id, seat, summary, i_type, priority, sprint, "ready", note, datetime.now().isoformat())
            )
            conn.commit()
        return issue_id

    def update_issue_status(self, issue_id: str, status: str, assignee: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if assignee:
                conn.execute("UPDATE issues SET status = ?, assignee = ? WHERE id = ?", (status, assignee, issue_id))
            else:
                conn.execute("UPDATE issues SET status = ? WHERE id = ?", (status, issue_id))
            conn.commit()

    def update_issue_resolution(self, issue_id: str, resolution: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET resolution = ? WHERE id = ?", (resolution, issue_id))
            conn.commit()

    def add_credits(self, issue_id: str, credits: float):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET credits_spent = credits_spent + ? WHERE id = ?", (credits, issue_id))
            conn.commit()

    def get_session_issues(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM issues WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_issue(self, issue_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single issue by its ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
            return dict(row) if row else None

    def get_build_issues(self, build_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC", (build_id,)).fetchall()
            return [dict(r) for r in rows]

    def reset_build_issues(self, build_id: str):
        """Flips all 'done' or 'in_progress' issues in a build back to 'ready' for re-run patterns."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET status = 'ready' WHERE build_id = ?", (build_id,))
            conn.commit()

    def add_comment(self, issue_id: str, author: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO comments (issue_id, author, content, created_at) VALUES (?, ?, ?, ?)",
                (issue_id, author, content, datetime.now().isoformat())
            )
            conn.commit()

    def get_comments(self, issue_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at ASC", (issue_id,)).fetchall()
            return [dict(r) for r in rows]
