import sqlite3
import json
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Any, Optional
from orket.core.contracts.repositories import CardRepository, SessionRepository, SnapshotRepository
from orket.schema import CardStatus

class SQLiteCardRepository(CardRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
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
                    verification_json TEXT,
                    metrics_json TEXT,
                    created_at DATETIME
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
                CREATE TABLE IF NOT EXISTS card_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT,
                    role TEXT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,)).fetchone()
            if not row: return None
            data = dict(row)
            # Deserialize complex types
            if data.get('verification_json'): data['verification'] = json.loads(data['verification_json'])
            if data.get('metrics_json'): data['metrics'] = json.loads(data['metrics_json'])
            return data

    def get_by_build(self, build_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC", (build_id,)).fetchall()
            results = []
            for r in rows:
                data = dict(r)
                if data.get('verification_json'): data['verification'] = json.loads(data['verification_json'])
                if data.get('metrics_json'): data['metrics'] = json.loads(data['metrics_json'])
                results.append(data)
            return results

    def save(self, card_data: Dict[str, Any]):
        summary = card_data.get('summary') or card_data.get('name') or "Unnamed Unit"
        v_json = json.dumps(card_data.get('verification', {}))
        m_json = json.dumps(card_data.get('metrics', {}))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO issues 
                   (id, session_id, build_id, seat, summary, type, priority, sprint, status, note, verification_json, metrics_json, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (card_data['id'], card_data.get('session_id'), card_data.get('build_id'), card_data['seat'], summary, 
                 card_data['type'], card_data['priority'], card_data.get('sprint'), card_data['status'], card_data.get('note'),
                 v_json, m_json, datetime.now(UTC).isoformat())
            )
            conn.commit()

    def update_status(self, card_id: str, status: CardStatus, assignee: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if assignee:
                conn.execute("UPDATE issues SET status = ?, assignee = ? WHERE id = ?", (status.value, assignee, card_id))
            else:
                conn.execute("UPDATE issues SET status = ? WHERE id = ?", (status.value, card_id))
            conn.commit()
        self.add_transaction(card_id, assignee or "system", f"Set Status to '{status.value}'")

    def add_transaction(self, card_id: str, role: str, action: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, role, action)
            )
            conn.commit()

    def get_card_history(self, card_id: str) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM card_transactions WHERE card_id = ? ORDER BY timestamp ASC", (card_id,)).fetchall()
            history = []
            for r in rows:
                ts = datetime.fromisoformat(r['timestamp'].replace(' ', 'T')).strftime("%m/%d/%Y %I:%M%p")
                history.append(f"{ts}: {r['role']} -> {r['action']}")
            return history

    def add_issue(self, session_id: str, seat: str, summary: str, i_type: str, priority: str):
        issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO issues (id, session_id, seat, summary, type, priority, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (issue_id, session_id, seat, summary, i_type, priority, "ready", datetime.now(UTC).isoformat())
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
                (card_id, author, content, datetime.now(UTC).isoformat())
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

    def get_session_issues(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM issues WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
            results = []
            for r in rows:
                data = dict(r)
                if data.get('verification_json'): data['verification'] = json.loads(data['verification_json'])
                if data.get('metrics_json'): data['metrics'] = json.loads(data['metrics_json'])
                results.append(data)
            return results

class SQLiteSessionRepository(SessionRepository):
    def __init__(self, db_path: str):
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
                    transcript TEXT,
                    start_time DATETIME,
                    end_time DATETIME
                )
            """)
            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    def start_session(self, session_id: str, data: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (id, type, name, department, status, task_input, start_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, data['type'], data['name'], data['department'], "Started", data['task_input'], datetime.now(UTC).isoformat())
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
                (status, json.dumps(transcript), datetime.now(UTC).isoformat(), session_id)
            )
            conn.commit()

class SQLiteSnapshotRepository(SnapshotRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_snapshots (
                    session_id TEXT PRIMARY KEY,
                    config_json TEXT,
                    log_history TEXT,
                    captured_at DATETIME
                )
            """)
            conn.commit()

    def record(self, session_id: str, config: Dict, logs: List[Dict]):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO session_snapshots (session_id, config_json, log_history, captured_at) VALUES (?, ?, ?, ?)",
                (session_id, json.dumps(config), json.dumps(logs), datetime.now(UTC).isoformat())
            )
            conn.commit()

    def get(self, session_id: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None
