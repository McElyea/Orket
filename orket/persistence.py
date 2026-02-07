import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

class PersistenceManager:
    def __init__(self, db_path: str = "orket_persistence.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 1. Sessions Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    name TEXT,
                    department TEXT,
                    status TEXT,
                    task_input TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_tokens INTEGER DEFAULT 0,
                    transcript_json TEXT
                )
            """)
            
            # 2. Cards Table (The Core Backlog)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    type TEXT DEFAULT 'story',
                    summary TEXT,
                    seat TEXT,
                    status TEXT DEFAULT 'ready',
                    priority TEXT DEFAULT 'Medium',
                    assignee TEXT,
                    reporter TEXT,
                    sprint TEXT,
                    labels TEXT,
                    due_date TEXT,
                    note TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            
            # Migration from Books to Cards
            conn.execute("CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY)")
            cursor = conn.execute("PRAGMA table_info(books)")
            if len(cursor.fetchall()) > 1:
                 print("  [DB_MIGRATE] Migrating legacy Books to Cards...")
                 conn.execute("INSERT INTO cards (id, session_id, type, summary, seat, status, priority, assignee, sprint, note, created_at, updated_at) "
                              "SELECT id, session_id, type, summary, seat, status, priority, assignee, sprint, note, created_at, updated_at FROM books")
                 conn.execute("DROP TABLE books")
            
            conn.commit()

    def start_session(self, session_id: str, run_type: str, name: str, department: str, task: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (id, type, name, department, status, task_input, start_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, run_type, name, department, "running", task, datetime.now().isoformat())
            )
            conn.commit()

    def add_card(self, session_id: str, seat: str, summary: str, card_type="story", priority="Medium", sprint=None, note=""):
        from datetime import datetime
        now = datetime.now()
        year_suffix = now.strftime("%y")
        
        # Get department from session to use as ID prefix
        session = self.get_session(session_id)
        dept_prefix = "UNK"
        if session and session.get("department"):
            dept_prefix = session["department"][:3].upper()
        
        id_prefix = f"{dept_prefix}{year_suffix}-"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Find the highest sequence number for this prefix
            cursor = conn.execute(
                "SELECT id FROM cards WHERE id LIKE ? ORDER BY id DESC LIMIT 1",
                (f"{id_prefix}%",)
            )
            row = cursor.fetchone()
            
            sequence = 1
            if row:
                last_id = row["id"]
                try:
                    last_seq = int(last_id.split("-")[1])
                    sequence = last_seq + 1
                except:
                    pass
            
            card_id = f"{id_prefix}{sequence:04d}"
            
            conn.execute(
                """INSERT INTO cards (id, session_id, type, summary, seat, status, priority, sprint, note, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (card_id, session_id, card_type, summary, seat, "ready", priority, sprint, note, datetime.now().isoformat(), datetime.now().isoformat())
            )
            conn.commit()
        return card_id

    def update_card_status(self, card_id: str, status: str, assignee: str = None):
        with sqlite3.connect(self.db_path) as conn:
            if assignee:
                conn.execute("UPDATE cards SET status = ?, assignee = ?, updated_at = ? WHERE id = ?", (status, assignee, datetime.now().isoformat(), card_id))
            else:
                conn.execute("UPDATE cards SET status = ?, updated_at = ? WHERE id = ?", (status, datetime.now().isoformat(), card_id))
            conn.commit()

    def get_session_cards(self, session_id: str) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM cards WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
            return [dict(r) for r in rows]

    def update_session_status(self, session_id: str, status: str, total_tokens: int = 0, transcript: Any = None):
        with sqlite3.connect(self.db_path) as conn:
            transcript_str = json.dumps(transcript) if transcript else None
            conn.execute(
                "UPDATE sessions SET status = ?, end_time = ?, total_tokens = ?, transcript_json = ? WHERE id = ?",
                (status, datetime.now().isoformat(), total_tokens, transcript_str, session_id)
            )
            conn.commit()

    def get_recent_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return dict(row) if row else None
