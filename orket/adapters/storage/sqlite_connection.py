from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite


async def ensure_wal_mode(conn: aiosqlite.Connection) -> str:
    cursor = await conn.execute("PRAGMA journal_mode=WAL;")
    row = await cursor.fetchone()
    mode = str((row[0] if row else "") or "").lower()
    if mode != "wal":
        raise RuntimeError(f"SQLite WAL mode was not enabled; journal_mode={mode or '<unknown>'}")
    return mode


@asynccontextmanager
async def connect_sqlite_wal(db_path: str | Path) -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(db_path, timeout=5.0) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await ensure_wal_mode(conn)
        yield conn


async def current_journal_mode(db_path: str | Path) -> str:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("PRAGMA journal_mode")
        row: Any = await cursor.fetchone()
    return str((row[0] if row else "") or "").lower()
