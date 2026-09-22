"""Owned offline SQLite snapshots and exclusive publication of a migrated store."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from contextlib import AsyncExitStack, asynccontextmanager, closing
from pathlib import Path

import aiosqlite

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.core.domain.outward_authorization import args_hash

side_effecting = True


def _logical_snapshot(path: Path) -> str:
    """Runs only in an owned thread; excludes migration metadata, not workload data."""
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        schema = list(
            conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master "
                "WHERE tbl_name != 'runtime_store_bindings' ORDER BY type, name"
            )
        )
        tables = {}
        for kind, name, _, _ in schema:
            if kind != "table":
                continue
            identifier = '"' + name.replace('"', '""') + '"'
            rows = [
                [{"blob": cell.hex()} if isinstance(cell, bytes) else cell for cell in row]
                for row in conn.execute("SELECT * FROM " + identifier)
            ]
            tables[name] = sorted(rows, key=lambda row: args_hash({"row": row}))
        return args_hash({"schema": schema, "tables": tables})


@asynccontextmanager
async def hold_offline_stores(paths: tuple[Path, ...]):
    """Refuse current SQLite writers; stopped-old-owner remains an offline precondition."""
    async with AsyncExitStack() as stack:
        connections = {}
        for path in dict.fromkeys(paths):
            if not await asyncio.to_thread(path.is_file):
                raise ValueError("E_RUNTIME_STORE_MIGRATION_SOURCE_MISSING")
            conn = await stack.enter_async_context(aiosqlite.connect(path, timeout=0))
            await conn.execute("BEGIN IMMEDIATE")
            connections[path] = conn
        yield connections


class RuntimeStoreMigrationIO:
    side_effecting = True

    async def snapshot_digest(self, path: Path) -> str:
        return await run_owned_thread(lambda: _logical_snapshot(path), label="runtime-store-snapshot")

    async def backup(self, source: Path, staging: Path) -> None:
        await run_owned_io(lambda: self._backup(source, staging), label="runtime-store-backup", preserve_failure=True)

    async def _backup(self, source: Path, staging: Path) -> None:
        await asyncio.to_thread(staging.parent.mkdir, parents=True, exist_ok=True)
        if await asyncio.to_thread(staging.exists):
            if await self.snapshot_digest(source) != await self.snapshot_digest(staging):
                raise ValueError("E_RUNTIME_STORE_MIGRATION_STAGING_CONFLICT")
            return
        await asyncio.to_thread(_reserve, staging)
        async with (
            aiosqlite.connect(source.as_uri() + "?mode=ro", uri=True) as original,
            aiosqlite.connect(staging) as copied,
        ):
            await original.backup(copied)
            await copied.commit()
        if await self.snapshot_digest(source) != await self.snapshot_digest(staging):
            raise ValueError("E_RUNTIME_STORE_MIGRATION_SNAPSHOT_MISMATCH")

    async def publish(self, staging: Path, target: Path) -> None:
        await run_owned_io(lambda: self._publish(staging, target), label="runtime-store-publish", preserve_failure=True)

    async def _publish(self, staging: Path, target: Path) -> None:
        async with aiosqlite.connect(staging) as conn:
            cursor = await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if (await cursor.fetchone())[0] != 0:
                raise ValueError("E_RUNTIME_STORE_MIGRATION_CHECKPOINT_BUSY")
            cursor = await conn.execute("PRAGMA journal_mode=DELETE")
            if (await cursor.fetchone())[0] != "delete":
                raise ValueError("E_RUNTIME_STORE_MIGRATION_CHECKPOINT_FAILED")
        await asyncio.to_thread(_publish, staging, target)

    async def discard_published_staging(self, staging: Path, target: Path) -> None:
        await run_owned_thread(lambda: _discard_alias(staging, target), label="runtime-store-staging-cleanup")


def _reserve(path: Path) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)


def _publish(staging: Path, target: Path) -> None:
    """A hard link publishes without replacing an unrelated target on either OS."""
    os.link(staging, target)
    staging.unlink()


def _discard_alias(staging: Path, target: Path) -> None:
    if staging.exists():
        if not staging.samefile(target):
            raise ValueError("E_RUNTIME_STORE_MIGRATION_STAGING_CONFLICT")
        staging.unlink()
