from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List

import aiosqlite

from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus


class CardMiscOps:
    """Miscellaneous card operations delegated from AsyncCardRepository."""

    def __init__(self, execute, get_by_build) -> None:
        self._execute = execute
        self._get_by_build = get_by_build

    async def add_transaction(self, card_id: str, role: str, action: str) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, role, action),
            )

        await self._execute(_op, commit=True)

    async def get_card_history(self, card_id: str) -> List[str]:
        async def _op(conn: aiosqlite.Connection) -> List[str]:
            cursor = await conn.execute("SELECT * FROM card_transactions WHERE card_id = ? ORDER BY timestamp ASC", (card_id,))
            rows = await cursor.fetchall()
            history: List[str] = []
            for row in rows:
                ts = datetime.fromisoformat(row["timestamp"].replace(" ", "T"))
                history.append(f"{ts.strftime('%m/%d/%Y %I:%M%p')}: {row['role']} -> {row['action']}")
            return history

        return await self._execute(_op, row_factory=True)

    async def reset_build(self, build_id: str) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute("UPDATE issues SET status = ? WHERE build_id = ?", (CardStatus.READY.value, build_id))

        await self._execute(_op, commit=True)

    async def add_comment(self, issue_id: str, author: str, content: str) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                "INSERT INTO comments (issue_id, author, content, created_at) VALUES (?, ?, ?, ?)",
                (issue_id, author, content, datetime.now(UTC).isoformat()),
            )

        await self._execute(_op, commit=True)

    async def get_comments(self, issue_id: str) -> List[Dict[str, Any]]:
        async def _op(conn: aiosqlite.Connection) -> List[Dict[str, Any]]:
            cursor = await conn.execute("SELECT * FROM comments WHERE issue_id = ? ORDER BY created_at ASC", (issue_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def add_credits(self, issue_id: str, amount: float) -> None:
        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute("UPDATE issues SET credits_spent = credits_spent + ? WHERE id = ?", (amount, issue_id))
            await conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (issue_id, "system", f"Reported {amount} credits"),
            )

        await self._execute(_op, commit=True)

    async def get_independent_ready_issues(self, build_id: str) -> List[IssueRecord]:
        all_issues = await self._get_by_build(build_id)
        done_ids = {issue.id for issue in all_issues if issue.status == CardStatus.DONE}
        ready_candidates: List[IssueRecord] = []
        for issue in all_issues:
            if issue.status == CardStatus.READY and all(dep_id in done_ids for dep_id in issue.depends_on):
                ready_candidates.append(issue)
        return ready_candidates
