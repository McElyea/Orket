from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.card_archive_ops import CardArchiveOps
from orket.adapters.storage.card_migrations import CardMigrations


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
