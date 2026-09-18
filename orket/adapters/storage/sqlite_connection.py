"""Owned SQLite connections with verified, bounded WAL-mode admission."""
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

_BUSY_TIMEOUT_MS = 5000
side_effecting = True  # Admission may change the database's persistent journal mode.


async def ensure_wal_mode(conn: aiosqlite.Connection) -> str:
    mode = await _read_journal_mode(conn)
    if mode != "wal":
        async with conn.execute("PRAGMA journal_mode=WAL;") as cursor:
            row = await cursor.fetchone()
            mode = str((row[0] if row else "") or "").lower()
    if mode != "wal":
        raise RuntimeError(f"SQLite WAL mode was not enabled; journal_mode={mode or '<unknown>'}")
    return mode


async def _read_journal_mode(conn: aiosqlite.Connection) -> str:
    async with conn.execute("PRAGMA journal_mode") as cursor:
        row = await cursor.fetchone()
    return str((row[0] if row else "") or "").lower()


@asynccontextmanager
async def connect_sqlite_wal(db_path: str | Path) -> AsyncIterator[aiosqlite.Connection]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _BUSY_TIMEOUT_MS / 1000
    while True:
        # SQLite can skip its busy handler during a journal-mode lock upgrade.
        # Drop that connection before a bounded retry; never replay caller work.
        async with aiosqlite.connect(db_path, timeout=0) as conn:
            try:
                await ensure_wal_mode(conn)
            except aiosqlite.OperationalError as exc:
                code = getattr(exc, "sqlite_errorcode", None)
                # Include native BUSY_RECOVERY while another WAL opener recovers.
                if not isinstance(code, int) or code & 0xFF != sqlite3.SQLITE_BUSY:
                    raise
                busy = exc
            else:
                await conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS};")
                yield conn
                return
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise busy
        await asyncio.sleep(min(0.01, remaining))


async def current_journal_mode(db_path: str | Path) -> str:
    async with aiosqlite.connect(db_path) as conn:
        return await _read_journal_mode(conn)


@asynccontextmanager
async def sqlite_connection_scope(
    db_path: str | Path, connection: aiosqlite.Connection | None = None, *, commit: bool = True,
) -> AsyncIterator[aiosqlite.Connection]:
    """Borrow an explicit transaction, or commit only the connection owned here."""
    if connection is not None:
        yield connection
        return
    async with connect_sqlite_wal(db_path) as owned:
        yield owned
        if commit:
            await owned.commit()
