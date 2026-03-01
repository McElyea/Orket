"""
Async Card Repository - The Reconstruction (V2)

Hardened for parallel execution with safe locking patterns.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import CardRecord, IssueRecord
from orket.schema import CardStatus

from .card_archive_ops import CardArchiveOps
from .card_migrations import CardMigrations
from .card_misc_ops import CardMiscOps


class AsyncCardRepository(CardRepository):
    """Async implementation of CardRepository using aiosqlite."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._migrations = CardMigrations()
        self._archive_ops = CardArchiveOps(self._execute)
        self._misc_ops = CardMiscOps(self._execute, self.get_by_build)

    def __getattr__(self, name: str) -> Any:
        delegated = {
            "archive_card": self._archive_ops.archive_card,
            "archive_cards": self._archive_ops.archive_cards,
            "archive_build": self._archive_ops.archive_build,
            "find_related_card_ids": self._archive_ops.find_related_card_ids,
            "add_transaction": self._misc_ops.add_transaction,
            "get_card_history": self._misc_ops.get_card_history,
            "reset_build": self._misc_ops.reset_build,
            "add_comment": self._misc_ops.add_comment,
            "get_comments": self._misc_ops.get_comments,
            "add_credits": self._misc_ops.add_credits,
            "get_independent_ready_issues": self._misc_ops.get_independent_ready_issues,
        }
        target = delegated.get(name)
        if target is not None:
            return target
        raise AttributeError(name)

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await self._migrations.ensure_initialized(conn)

    async def _execute(
        self,
        operation,
        *,
        row_factory: bool = False,
        commit: bool = False,
    ):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                if row_factory:
                    conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                result = await operation(conn)
                if commit:
                    await conn.commit()
                return result

    async def get_by_id(self, card_id: str) -> Optional[IssueRecord]:
        async def _op(conn: aiosqlite.Connection) -> Optional[IssueRecord]:
            cursor = await conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return IssueRecord.model_validate(self._deserialize_row(dict(row)))

        return await self._execute(_op, row_factory=True)

    async def get_by_build(self, build_id: str) -> List[IssueRecord]:
        async def _op(conn: aiosqlite.Connection) -> List[IssueRecord]:
            cursor = await conn.execute("SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC", (build_id,))
            rows = await cursor.fetchall()
            return [IssueRecord.model_validate(self._deserialize_row(dict(row))) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def list_cards(
        self,
        *,
        build_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        where_clauses: List[str] = []
        params: List[Any] = []

        if build_id:
            where_clauses.append("build_id = ?")
            params.append(build_id)
        if session_id:
            where_clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            where_clauses.append("LOWER(status) = ?")
            params.append(str(status).lower())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = (
            "SELECT * FROM issues "
            f"{where_sql} "
            "ORDER BY datetime(created_at) DESC, id DESC "
            "LIMIT ? OFFSET ?"
        )
        params.extend([max(1, int(limit)), max(0, int(offset))])

        async def _op(conn: aiosqlite.Connection) -> List[Dict[str, Any]]:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [self._deserialize_row(dict(row)) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save(self, record: IssueRecord | Dict[str, Any]) -> None:
        if isinstance(record, dict):
            record = IssueRecord.model_validate(record)

        summary = record.summary or "Unnamed Unit"
        v_json = json.dumps(record.verification)
        m_json = json.dumps(record.metrics)
        d_json = json.dumps(record.depends_on)

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """INSERT OR REPLACE INTO issues
                   (id, session_id, build_id, seat, summary, type, priority, sprint,
                    status, note, retry_count, max_retries, verification_json, metrics_json, depends_on_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    record.session_id,
                    record.build_id,
                    record.seat,
                    summary,
                    record.type.value if hasattr(record.type, "value") else str(record.type),
                    record.priority,
                    record.sprint,
                    record.status.value if hasattr(record.status, "value") else str(record.status),
                    record.note,
                    record.retry_count,
                    record.max_retries,
                    v_json,
                    m_json,
                    d_json,
                    record.created_at or datetime.now(UTC).isoformat(),
                ),
            )

        await self._execute(_op, commit=True)

    async def update_status(
        self,
        card_id: str,
        status: CardStatus,
        assignee: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            prev_cursor = await conn.execute("SELECT status FROM issues WHERE id = ?", (card_id,))
            prev_row = await prev_cursor.fetchone()
            prev_status = prev_row["status"] if prev_row else None

            if assignee:
                await conn.execute("UPDATE issues SET status = ?, assignee = ? WHERE id = ?", (status.value, assignee, card_id))
            else:
                await conn.execute("UPDATE issues SET status = ? WHERE id = ?", (status.value, card_id))

            action = f"Set Status to '{status.value}'"
            if prev_status is not None:
                action += f" (from '{prev_status}')"
            if reason:
                action += f" reason='{reason}'"
            if metadata:
                action += f" meta={json.dumps(metadata, ensure_ascii=False, sort_keys=True)}"

            await conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, assignee or "system", action),
            )

        await self._execute(_op, row_factory=True, commit=True)

    def _deserialize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        for field in ["verification_json", "metrics_json", "depends_on_json"]:
            target = field.replace("_json", "")
            if row.get(field):
                try:
                    row[target] = json.loads(row[field])
                except json.JSONDecodeError:
                    row[target] = [] if target == "depends_on" else {}
            else:
                row[target] = [] if target == "depends_on" else {}
        return row
