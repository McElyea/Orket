from __future__ import annotations

from typing import Any, cast

import aiosqlite

from orket.schema import CardStatus


class CardArchiveOps:
    """Archive and related-card lookup operations for AsyncCardRepository."""

    def __init__(self, execute: Any) -> None:
        self._execute = execute

    async def archive_card(self, card_id: str, archived_by: str = "system", reason: str | None = None) -> bool:
        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute("SELECT id FROM issues WHERE id = ?", (card_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            await conn.execute(
                "UPDATE issues SET status = ?, assignee = ? WHERE id = ?",
                (CardStatus.ARCHIVED.value, archived_by, card_id),
            )
            action = "Archived card"
            if reason:
                action += f" ({reason})"
            await conn.execute(
                "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                (card_id, archived_by, action),
            )
            return True

        return cast(bool, await self._execute(_op, commit=True))

    async def archive_cards(
        self,
        card_ids: list[str],
        archived_by: str = "system",
        reason: str | None = None,
    ) -> dict[str, list[str]]:
        archived: list[str] = []
        missing: list[str] = []
        for card_id in card_ids:
            ok = await self.archive_card(card_id, archived_by=archived_by, reason=reason)
            if ok:
                archived.append(card_id)
            else:
                missing.append(card_id)
        return {"archived": archived, "missing": missing}

    async def archive_build(
        self,
        build_id: str,
        archived_by: str = "system",
        reason: str | None = None,
    ) -> int:
        async def _op(conn: aiosqlite.Connection) -> int:
            cursor = await conn.execute("SELECT id FROM issues WHERE build_id = ?", (build_id,))
            rows = await cursor.fetchall()
            if not rows:
                return 0
            ids = [row["id"] for row in rows]
            await conn.execute(
                "UPDATE issues SET status = ?, assignee = ? WHERE build_id = ?",
                (CardStatus.ARCHIVED.value, archived_by, build_id),
            )
            action = f"Archived build '{build_id}'"
            if reason:
                action += f" ({reason})"
            for card_id in ids:
                await conn.execute(
                    "INSERT INTO card_transactions (card_id, role, action) VALUES (?, ?, ?)",
                    (card_id, archived_by, action),
                )
            return len(ids)

        return cast(int, await self._execute(_op, row_factory=True, commit=True))

    async def find_related_card_ids(self, tokens: list[str], limit: int = 500) -> list[str]:
        normalized = [token.strip().lower() for token in tokens if token and token.strip()]
        if not normalized:
            return []

        clauses: list[str] = []
        params: list[Any] = []
        for token in normalized:
            like = f"%{token}%"
            clauses.append(
                "(LOWER(id) LIKE ? OR LOWER(COALESCE(build_id, '')) LIKE ? OR "
                "LOWER(COALESCE(summary, '')) LIKE ? OR LOWER(COALESCE(note, '')) LIKE ?)"
            )
            params.extend([like, like, like, like])

        query = f"""
            SELECT id
            FROM issues
            WHERE {" OR ".join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)

        async def _op(conn: aiosqlite.Connection) -> list[str]:
            cursor = await conn.execute(query, tuple(params))
            rows = await cursor.fetchall()
            return [row["id"] for row in rows]

        return cast(list[str], await self._execute(_op, row_factory=True))
