import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from orket.repositories import CardRepository, SessionRepository, SnapshotRepository
from orket.schema import CardStatus

class SQLiteCardRepository(CardRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,)).fetchone()
            return dict(row) if row else None

    def get_by_build(self, build_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC", (build_id,)).fetchall()
            return [dict(r) for r in rows]

    def save(self, card_data: Dict[str, Any]):
        summary = card_data.get('summary') or card_data.get('name') or "Unnamed Unit"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO issues (id, session_id, build_id, seat, summary, type, priority, sprint, status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (card_data['id'], card_data['session_id'], card_data['build_id'], card_data['seat'], summary, 
                 card_data['type'], card_data['priority'], card_data.get('sprint'), card_data['status'], card_data.get('note'), datetime.now().isoformat())
            )
            conn.commit()

    def update_status(self, card_id: str, status: CardStatus, assignee: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if assignee:
                conn.execute("UPDATE issues SET status = ?, assignee = ? WHERE id = ?", (status.value, assignee, card_id))
            else:
                conn.execute("UPDATE issues SET status = ? WHERE id = ?", (status.value, card_id))
            conn.commit()
        
        # Record Transaction
        self.add_transaction(card_id, assignee or "system", f"Set Status to '{status.value}'")

    def add_transaction(self, card_id: str, role: str, action: str):
        """Records a DateTime: Role -> Action entry in the audit ledger."""
        with sqlite3.connect(self.db_path) as conn:
            # Ensure table exists (simplified for now, usually done in init)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS card_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT,
                    role TEXT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, role, action)
            )
            conn.commit()

    def get_card_history(self, card_id: str) -> List[str]:
        """Returns history formatted as: 2/8/2026 3:48PM: Coder -> Set Status to 'Code Review'"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM card_transactions WHERE card_id = ? ORDER BY timestamp ASC", (card_id,)).fetchall()
            history = []
            for r in rows:
                # Basic formatting
                ts = datetime.fromisoformat(r['timestamp'].replace(' ', 'T')).strftime("%m/%d/%Y %I:%M%p")
                history.append(f"{ts}: {r['role']} -> {r['action']}")
            return history

    def add_issue(self, session_id: str, seat: str, summary: str, i_type: str, priority: str):
        issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO issues (id, session_id, seat, summary, type, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (issue_id, session_id, seat, summary, i_type, priority, "ready", datetime.now().isoformat())
            )
            conn.commit()
        return issue_id

    def update_issue_resolution(self, card_id: str, resolution: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET resolution = ? WHERE id = ?", (resolution, card_id))
            conn.commit()

    def add_credits(self, card_id: str, amount: float):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET credits_spent = credits_spent + ? WHERE id = ?", (amount, card_id))
            conn.commit()

    def add_comment(self, card_id: str, author: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO comments (issue_id, author, content, created_at) VALUES (?, ?, ?, ?)",
                (card_id, author, content, datetime.now().isoformat())
            )
            conn.commit()

    def get_comments(self, card_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at ASC", (card_id,)).fetchall()
            return [dict(r) for r in rows]

    def reset_build(self, build_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE issues SET status = 'ready' WHERE build_id = ?", (build_id,))
            conn.commit()

class SQLiteSessionRepository(SessionRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def start_session(self, session_id: str, data: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, type, name, department, status, task_input, start_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, data['type'], data['name'], data['department'], "Started", data['task_input'], datetime.now().isoformat())
            )
            conn.commit()

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def complete_session(self, session_id: str, status: str, transcript: List[Dict]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, transcript = ?, end_time = ? WHERE id = ?",
                (status, json.dumps(transcript), datetime.now().isoformat(), session_id)
            )
            conn.commit()

class SQLiteSnapshotRepository(SnapshotRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def record(self, session_id: str, config: Dict, logs: List[Dict]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_snapshots (session_id, config_json, log_history, captured_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(config), json.dumps(logs), datetime.now().isoformat())
            )
            conn.commit()

    def get(self, session_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None
