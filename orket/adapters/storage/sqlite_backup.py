from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import aiosqlite

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots

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
    input_roots = capture_file_roots([source, backup, destination])
    source, backup, destination = await run_owned_thread(
        lambda: tuple(path.resolve() for path in input_roots), label="sqlite-migration-paths")
    if len({source, backup, destination}) != 3:
        raise ValueError("E_OUTWARD_MIGRATION_PATH_COLLISION")
    paths = (source, backup, destination)
    if any(path in sqlite_files(other)[1:] for path in paths for other in paths if path != other):
        raise ValueError("E_OUTWARD_MIGRATION_PATH_COLLISION: SQLite sidecar")
    if not await run_owned_thread(source.is_file, label="sqlite-migration-source"):
        raise FileNotFoundError(source)
    for path in (*sqlite_files(backup), *sqlite_files(destination)):
        if await run_owned_thread(path.exists, label="sqlite-migration-collision"):
            raise FileExistsError(path)
    for path in (backup, destination):
        await run_owned_thread(partial(path.parent.mkdir, parents=True, exist_ok=True), label="sqlite-migration-parent")
        await run_owned_thread(partial(path.touch, exist_ok=False), label="sqlite-migration-create")
    await copy_sqlite_snapshot(source, backup)
    await copy_sqlite_snapshot(backup, destination)
    return SQLiteMigrationCopy(source, backup, destination, await run_owned_thread(partial(_file_digest, backup), label="sqlite-migration-digest"))


async def copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    """SQLite backup includes committed WAL pages; copying the raw DB file does not."""
    source_uri = source.as_uri() + "?mode=ro"
    destination, = capture_file_roots([destination])

    async def copy_owned() -> None:
        async with (
            aiosqlite.connect(source_uri, uri=True) as reader,
            aiosqlite.connect(destination) as writer,
        ):
            await reader.backup(writer)

    await run_owned_io(copy_owned, label="sqlite-snapshot-copy", preserve_failure=True)


def _file_digest(path: Path) -> str:
    # Called only in the owned filesystem worker after both backup connections close.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
