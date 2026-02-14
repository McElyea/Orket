"""
Async Repositories for Session and Snapshot persistence.
"""
from __future__ import annotations
import aiosqlite
import json
import asyncio
import uuid
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


class AsyncRunLedgerRepository:
    """
    Unified run ledger for success, failure, and incomplete outcomes.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        if self._initialized:
            return
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_ledger (
                session_id TEXT PRIMARY KEY,
                run_type TEXT,
                run_name TEXT,
                department TEXT,
                build_id TEXT,
                status TEXT,
                failure_class TEXT,
                failure_reason TEXT,
                summary_json TEXT,
                artifact_json TEXT,
                started_at DATETIME,
                ended_at DATETIME,
                updated_at DATETIME
            )
            """
        )
        await conn.commit()
        self._initialized = True

    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO run_ledger
                    (session_id, run_type, run_name, department, build_id, status, failure_class, failure_reason,
                     summary_json, artifact_json, started_at, ended_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        run_type,
                        run_name,
                        department,
                        build_id,
                        "running",
                        None,
                        None,
                        json.dumps(summary or {}),
                        json.dumps(artifacts or {}),
                        now,
                        None,
                        now,
                    ),
                )
                await conn.commit()

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: Optional[str] = None,
        failure_reason: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)

                if summary is None and artifacts is None:
                    await conn.execute(
                        """
                        UPDATE run_ledger
                        SET status = ?, failure_class = ?, failure_reason = ?, ended_at = ?, updated_at = ?
                        WHERE session_id = ?
                        """,
                        (
                            status,
                            failure_class,
                            failure_reason,
                            now,
                            now,
                            session_id,
                        ),
                    )
                else:
                    cursor = await conn.execute(
                        "SELECT summary_json, artifact_json FROM run_ledger WHERE session_id = ?",
                        (session_id,),
                    )
                    row = await cursor.fetchone()
                    merged_summary: Dict[str, Any] = {}
                    merged_artifacts: Dict[str, Any] = {}
                    if row:
                        if row[0]:
                            try:
                                merged_summary = json.loads(row[0])
                            except json.JSONDecodeError:
                                merged_summary = {}
                        if row[1]:
                            try:
                                merged_artifacts = json.loads(row[1])
                            except json.JSONDecodeError:
                                merged_artifacts = {}
                    if summary:
                        merged_summary.update(summary)
                    if artifacts:
                        merged_artifacts.update(artifacts)

                    await conn.execute(
                        """
                        UPDATE run_ledger
                        SET status = ?, failure_class = ?, failure_reason = ?, summary_json = ?, artifact_json = ?,
                            ended_at = ?, updated_at = ?
                        WHERE session_id = ?
                        """,
                        (
                            status,
                            failure_class,
                            failure_reason,
                            json.dumps(merged_summary),
                            json.dumps(merged_artifacts),
                            now,
                            now,
                            session_id,
                        ),
                    )
                await conn.commit()

    async def get_run(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                cursor = await conn.execute("SELECT * FROM run_ledger WHERE session_id = ?", (session_id,))
                row = await cursor.fetchone()
                if not row:
                    return None
                data = dict(row)
                for field in ("summary_json", "artifact_json"):
                    if data.get(field):
                        try:
                            data[field] = json.loads(data[field])
                        except json.JSONDecodeError:
                            data[field] = {}
                    else:
                        data[field] = {}
                return data


class AsyncPendingGateRepository:
    """
    Persistent ledger for pending gate/approval/review requests.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection):
        if self._initialized:
            return
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_gate_requests (
                request_id TEXT PRIMARY KEY,
                session_id TEXT,
                issue_id TEXT,
                seat_name TEXT,
                gate_mode TEXT,
                request_type TEXT,
                reason TEXT,
                payload_json TEXT,
                status TEXT,
                resolution_json TEXT,
                created_at DATETIME,
                updated_at DATETIME,
                resolved_at DATETIME
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_gate_requests_session "
            "ON pending_gate_requests(session_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pending_gate_requests_status "
            "ON pending_gate_requests(status)"
        )
        await conn.commit()
        self._initialized = True

    async def create_request(
        self,
        *,
        session_id: str,
        issue_id: str,
        seat_name: str,
        gate_mode: str,
        request_type: str,
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        request_id = str(uuid.uuid4())[:8]
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    """
                    INSERT INTO pending_gate_requests
                    (request_id, session_id, issue_id, seat_name, gate_mode, request_type, reason,
                     payload_json, status, resolution_json, created_at, updated_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        session_id,
                        issue_id,
                        seat_name,
                        gate_mode,
                        request_type,
                        reason,
                        json.dumps(payload or {}),
                        "pending",
                        None,
                        now,
                        now,
                        None,
                    ),
                )
                await conn.commit()
        return request_id

    async def resolve_request(
        self,
        *,
        request_id: str,
        status: str,
        resolution: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await self._ensure_initialized(conn)
                await conn.execute(
                    """
                    UPDATE pending_gate_requests
                    SET status = ?, resolution_json = ?, updated_at = ?, resolved_at = ?
                    WHERE request_id = ?
                    """,
                    (status, json.dumps(resolution or {}), now, now, request_id),
                )
                await conn.commit()

    async def list_requests(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)

                where_parts: List[str] = []
                params: List[Any] = []
                if session_id:
                    where_parts.append("session_id = ?")
                    params.append(session_id)
                if status:
                    where_parts.append("status = ?")
                    params.append(status)

                where_clause = ""
                if where_parts:
                    where_clause = "WHERE " + " AND ".join(where_parts)

                params.append(limit)
                cursor = await conn.execute(
                    f"""
                    SELECT * FROM pending_gate_requests
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    tuple(params),
                )
                rows = await cursor.fetchall()
                results: List[Dict[str, Any]] = []
                for row in rows:
                    item = dict(row)
                    for key in ("payload_json", "resolution_json"):
                        if item.get(key):
                            try:
                                item[key] = json.loads(item[key])
                            except json.JSONDecodeError:
                                item[key] = {}
                        else:
                            item[key] = {}
                    results.append(item)
                return results
