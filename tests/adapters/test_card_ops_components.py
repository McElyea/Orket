from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.card_archive_ops import CardArchiveOps
from orket.adapters.storage.card_migrations import CardMigrations
from orket.adapters.storage.card_misc_ops import CardMiscOps
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus, CardType


@pytest.mark.asyncio
async def test_card_migrations_creates_issues_table(tmp_path: Path) -> None:
    db_path = tmp_path / "cards.db"
    async with aiosqlite.connect(str(db_path)) as conn:
        migrations = CardMigrations()
        await migrations.ensure_initialized(conn)
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issues'")
        row = await cursor.fetchone()
        assert row is not None


@pytest.mark.asyncio
async def test_card_archive_ops_archive_cards_batches_results() -> None:
    calls: list[str] = []

    async def _execute(operation, *, row_factory=False, commit=False):
        class _Conn:
            async def execute(self, _sql, _args):
                calls.append(_args[0])
                class _Cursor:
                    async def fetchone(self):
                        return {"id": _args[0]} if _args[0] != "missing" else None
                return _Cursor()
        return await operation(_Conn())

    ops = CardArchiveOps(_execute)
    result = await ops.archive_cards(["a", "missing"])
    assert result == {"archived": ["a"], "missing": ["missing"]}


@pytest.mark.asyncio
async def test_card_misc_ops_independent_ready_filter() -> None:
    async def _execute(_operation, *, row_factory=False, commit=False):
        return []

    async def _get_by_build(_build_id: str):
        return [
            IssueRecord(
                id="D1",
                session_id="S",
                build_id="B",
                seat="dev",
                summary="done",
                type=CardType.ISSUE,
                priority="p1",
                sprint="s1",
                status=CardStatus.DONE,
                note="",
                depends_on=[],
            ),
            IssueRecord(
                id="R1",
                session_id="S",
                build_id="B",
                seat="dev",
                summary="ready",
                type=CardType.ISSUE,
                priority="p1",
                sprint="s1",
                status=CardStatus.READY,
                note="",
                depends_on=["D1"],
            ),
        ]

    ops = CardMiscOps(_execute, _get_by_build)
    ready = await ops.get_independent_ready_issues("B")
    assert [issue.id for issue in ready] == ["R1"]
