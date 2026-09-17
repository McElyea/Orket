"""
Async Card Repository - The Reconstruction (V2)

Hardened for parallel execution with safe locking patterns.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite

from orket.core.contracts.card_completion_commit import (
    CardCompletionAuthority,
    CardCompletionContext,
    CardCompletionReceipt,
    CardCompletionRejected,
    CardCompletionRequest,
)
from orket.core.contracts.repositories import CardRepository
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus

from .card_archive_ops import CardArchiveOps
from .card_migrations import CardMigrations
from .card_misc_ops import CardMiscOps
from .card_record_codec import deserialize_card_row
from .card_write_ops import begin_completion_attempt, read_completion_receipt, save_card, update_card_status
from .sqlite_connection import connect_sqlite_wal

ResultT = TypeVar("ResultT")


class AsyncCardRepository(CardRepository):
    """Async implementation of CardRepository using aiosqlite."""

    side_effecting = True

    def __init__(self, db_path: str | Path, *, completion_authority: CardCompletionAuthority | None = None) -> None:
        self.db_path = str(db_path)
        self._completion_authority = completion_authority
        self._write_lock = asyncio.Lock()
        self._initialization_lock = asyncio.Lock()
        self._initialized = False
        self._migrations = CardMigrations()
        self._archive_ops = CardArchiveOps(self._execute)
        self._misc_ops = CardMiscOps(self._execute)

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        async with self._initialization_lock:
            if not self._initialized:
                await self._migrations.ensure_initialized(conn)
                self._initialized = True

    async def archive_card(self, card_id: str, archived_by: str = "system", reason: str | None = None) -> bool:
        return await self._archive_ops.archive_card(card_id, archived_by=archived_by, reason=reason)

    async def archive_cards(
        self,
        card_ids: list[str],
        archived_by: str = "system",
        reason: str | None = None,
    ) -> dict[str, list[str]]:
        return await self._archive_ops.archive_cards(card_ids, archived_by=archived_by, reason=reason)

    async def archive_build(
        self,
        build_id: str,
        archived_by: str = "system",
        reason: str | None = None,
    ) -> int:
        return await self._archive_ops.archive_build(build_id, archived_by=archived_by, reason=reason)

    async def find_related_card_ids(self, tokens: list[str], limit: int = 500) -> list[str]:
        return await self._archive_ops.find_related_card_ids(tokens, limit=limit)

    async def add_transaction(self, card_id: str, role: str, action: str) -> None:
        await self._misc_ops.add_transaction(card_id, role, action)

    async def get_card_history(self, card_id: str) -> list[str]:
        return await self._misc_ops.get_card_history(card_id)

    async def reset_build(self, build_id: str) -> None:
        await self._misc_ops.reset_build(build_id)

    async def add_comment(self, issue_id: str, author: str, content: str) -> None:
        await self._misc_ops.add_comment(issue_id, author, content)

    async def get_comments(self, issue_id: str) -> list[dict[str, Any]]:
        return await self._misc_ops.get_comments(issue_id)

    async def add_credits(self, issue_id: str, amount: float) -> None:
        await self._misc_ops.add_credits(issue_id, amount)

    async def _execute(
        self,
        operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]],
        *,
        row_factory: bool = False,
        commit: bool = False,
        write: bool = False,
    ) -> ResultT:
        async def _run_operation() -> ResultT:
            async with self._connection(row_factory=row_factory, commit=commit, write=write) as conn:
                result = await operation(conn)
                return result

        if commit or write:
            async with self._write_lock:
                return await _run_operation()
        return await _run_operation()

    @asynccontextmanager
    async def _connection(self, *, row_factory: bool, commit: bool, write: bool) -> AsyncIterator[aiosqlite.Connection]:
        async with connect_sqlite_wal(self.db_path) as conn:
            if row_factory:
                conn.row_factory = aiosqlite.Row
            await self._ensure_initialized(conn)
            if commit or write:
                await conn.execute("BEGIN IMMEDIATE")
            yield conn
            if commit:
                await conn.commit()

    @asynccontextmanager
    async def completion_write_guard(self) -> AsyncIterator[None]:
        async with self._write_lock, self._connection(row_factory=False, commit=True, write=True):
            yield

    async def get_by_id(self, card_id: str) -> IssueRecord | None:
        async def _op(conn: aiosqlite.Connection) -> IssueRecord | None:
            cursor = await conn.execute("SELECT * FROM issues WHERE id = ?", (card_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return IssueRecord.model_validate(deserialize_card_row(dict(row)))

        return await self._execute(_op, row_factory=True)

    async def get_by_build(self, build_id: str) -> list[IssueRecord]:
        return await self._get_scoped_cards("build_id", build_id)

    async def get_by_session(self, session_id: str) -> list[IssueRecord]:
        return await self._get_scoped_cards("session_id", session_id)

    async def _get_scoped_cards(self, column: str, value: str) -> list[IssueRecord]:
        queries = {
            "build_id": "SELECT * FROM issues WHERE build_id = ? ORDER BY created_at ASC",
            "session_id": "SELECT * FROM issues WHERE session_id = ? ORDER BY created_at ASC",
        }

        async def _op(conn: aiosqlite.Connection) -> list[IssueRecord]:
            cursor = await conn.execute(queries[column], (value,))
            rows = await cursor.fetchall()
            return [IssueRecord.model_validate(deserialize_card_row(dict(row))) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def list_cards(
        self,
        *,
        build_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        where_clauses: list[str] = []
        params: list[Any] = []

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
        query = f"SELECT * FROM issues {where_sql} ORDER BY datetime(created_at) DESC, id DESC LIMIT ? OFFSET ?"
        params.extend([max(1, int(limit)), max(0, int(offset))])

        async def _op(conn: aiosqlite.Connection) -> list[dict[str, Any]]:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [deserialize_card_row(dict(row)) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def save(self, record: IssueRecord | dict[str, Any]) -> None:
        record = IssueRecord.model_validate(record).model_copy(deep=True)

        async def _op(conn: aiosqlite.Connection) -> None:
            await save_card(conn, record)

        await self._execute(_op, row_factory=True, commit=True)

    async def begin_completion_attempt(self, context: CardCompletionContext) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await begin_completion_attempt(conn, context)

        await self._execute(_op, row_factory=True, commit=True)

    async def read_completion_receipt(self, card_id: str) -> CardCompletionReceipt | None:
        path = await asyncio.to_thread(Path(self.db_path).resolve)
        try:
            async with aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA query_only=ON")
                snapshot = await read_completion_receipt(conn, card_id)
            if snapshot is None:
                return None
            record, receipt = snapshot
            if self._completion_authority is None:
                raise CardCompletionRejected("E_CARD_COMPLETION_AUTHORITY_MISSING")
            decision = await self._completion_authority.inspect_completion_receipt(record=record, receipt=receipt)
            if not decision.sufficient:
                raise CardCompletionRejected("E_CARD_COMPLETION_RECEIPT_EVIDENCE_UNVERIFIABLE", decision)
            return receipt
        except CardCompletionRejected:
            raise
        except (aiosqlite.Error, ValueError, TypeError) as exc:
            raise CardCompletionRejected(f"E_CARD_COMPLETION_RECEIPT_UNVERIFIABLE:{exc}") from exc

    async def update_status(
        self,
        card_id: str,
        status: CardStatus,
        assignee: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        completion_request: CardCompletionRequest | None = None,
    ) -> CardCompletionReceipt | None:
        async def _op(conn: aiosqlite.Connection) -> CardCompletionReceipt | None:
            return await update_card_status(
                conn, card_id=card_id, status=status, assignee=assignee, reason=reason, metadata=metadata,
                request=completion_request, authority=self._completion_authority,
            )

        return await self._execute(_op, row_factory=True, commit=True)
