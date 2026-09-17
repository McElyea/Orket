"""Owned crash rehearsal: pause the real CLI after its first batch of SQLite commitment writes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiosqlite

from scripts.governance.migrate_outward_ledger import main


def run() -> int:
    reached = Path(sys.argv[1])
    del sys.argv[1]
    original = aiosqlite.Connection.executemany

    async def pause_after_writes(connection, sql, parameters):
        result = await original(connection, sql, parameters)
        if sql.startswith("INSERT INTO outward_ledger_commits_v2"):
            assert connection.in_transaction
            count = await (await connection.execute("SELECT COUNT(*) FROM outward_ledger_commits_v2")).fetchone()
            pending = reached.with_suffix(".pending")
            await asyncio.to_thread(pending.write_text, str(count[0]), encoding="utf-8")
            await asyncio.to_thread(pending.replace, reached)
            await asyncio.Event().wait()
        return result

    aiosqlite.Connection.executemany = pause_after_writes
    try:
        return main()
    finally:
        aiosqlite.Connection.executemany = original


if __name__ == "__main__":
    raise SystemExit(run())
