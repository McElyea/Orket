from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

side_effecting = True


@dataclass(frozen=True)
class SQLiteMigrationCopy:
    source: Path
    backup: Path
    destination: Path
    backup_sha256: str


def sqlite_files(path: Path) -> tuple[Path, ...]:
    return (path, *(path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal")))


async def prepare_sqlite_migration_copy(
    *, source: Path, backup: Path, destination: Path, writers_stopped: bool,
) -> SQLiteMigrationCopy:
    if not writers_stopped:
        raise ValueError("E_OUTWARD_WRITERS_MUST_BE_STOPPED")
    source, backup, destination = [await asyncio.to_thread(path.resolve) for path in (source, backup, destination)]
    if len({source, backup, destination}) != 3:
        raise ValueError("E_OUTWARD_MIGRATION_PATH_COLLISION")
    paths = (source, backup, destination)
    if any(path in sqlite_files(other)[1:] for path in paths for other in paths if path != other):
        raise ValueError("E_OUTWARD_MIGRATION_PATH_COLLISION: SQLite sidecar")
    if not await asyncio.to_thread(source.is_file):
        raise FileNotFoundError(source)
    for path in (*sqlite_files(backup), *sqlite_files(destination)):
        if await asyncio.to_thread(path.exists):
            raise FileExistsError(path)
    for path in (backup, destination):
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.touch, exist_ok=False)
    await copy_sqlite_snapshot(source, backup)
    await copy_sqlite_snapshot(backup, destination)
    return SQLiteMigrationCopy(source, backup, destination, await asyncio.to_thread(_file_digest, backup))


async def copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    """SQLite backup includes committed WAL pages; copying the raw DB file does not."""
    async with (
        aiosqlite.connect(source.as_uri() + "?mode=ro", uri=True) as reader,
        aiosqlite.connect(destination) as writer,
    ):
        await reader.backup(writer)


def _file_digest(path: Path) -> str:
    # Called only in the owned filesystem worker after both backup connections close.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
