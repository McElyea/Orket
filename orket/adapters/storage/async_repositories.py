"""
Async Repositories for Session and Snapshot persistence.
"""
from __future__ import annotations
import aiosqlite
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC

from orket.core.contracts.repositories import SessionRepository, SnapshotRepository

class AsyncSessionRepository(SessionRepository):
    """
    Async implementation of SessionRepository using aiosqlite.
    """
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        if self._initialized:
            return
        await conn.execute("""
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
        await conn.commit()
        self._initialized = True

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def start_session(self, session_id: str, data: Dict[str, Any]):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    "INSERT OR IGNORE INTO sessions (id, type, name, department, status, task_input, start_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, data['type'], data['name'], data['department'], "Started", data['task_input'], datetime.now(UTC).isoformat())
                )
                await conn.commit()

    async def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,))
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def complete_session(self, session_id: str, status: str, transcript: List[Dict]):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    "UPDATE sessions SET status = ?, transcript = ?, end_time = ? WHERE id = ?",
                    (status, json.dumps(transcript), datetime.now(UTC).isoformat(), session_id)
                )
                await conn.commit()

class AsyncSnapshotRepository(SnapshotRepository):
    """
    Async implementation of SnapshotRepository using aiosqlite.
    """
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        if self._initialized:
            return
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS session_snapshots (
                session_id TEXT PRIMARY KEY,
                config_json TEXT,
                log_history TEXT,
                captured_at DATETIME
            )
        """)
        await conn.commit()
        self._initialized = True

    async def record(self, session_id: str, config: Dict, logs: List[Dict]):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    "INSERT OR REPLACE INTO session_snapshots (session_id, config_json, log_history, captured_at) VALUES (?, ?, ?, ?)",
                    (session_id, json.dumps(config), json.dumps(logs), datetime.now(UTC).isoformat())
                )
                await conn.commit()

    async def get(self, session_id: str) -> Optional[Dict]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM session_snapshots WHERE session_id = ?", (session_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None

class AsyncSuccessRepository:
    """
    Success Ledger - Irreversible Success Criterion enforcement.
    One row per run. Incomplete until a success record is written.
    """
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        if self._initialized:
            return
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS success_ledger (
                session_id TEXT PRIMARY KEY,
                success_type TEXT, -- e.g. 'PR_MERGED', 'ARTIFACT_GENERATED', 'FIT_VERIFIED'
                artifact_ref TEXT, -- Path, PR URL, or Hash
                human_ack TEXT,    -- Nullable: 'Yes'/'No' from the judge
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()
        self._initialized = True

    async def record_success(self, session_id: str, success_type: str, artifact_ref: str, human_ack: Optional[str] = None):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    "INSERT OR REPLACE INTO success_ledger (session_id, success_type, artifact_ref, human_ack) VALUES (?, ?, ?, ?)",
                    (session_id, success_type, artifact_ref, human_ack)
                )
                await conn.commit()
