"""Stage the old layout/request contract with real card execution and SQLite copies."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.application.services.runtime_store_migration_service import RuntimeStoreMigrationService
from tests.integration.test_runtime_store_binding import bound_engine, pause, stage_project


async def legacy_pause(root, monkeypatch, *, workspace=None):
    await stage_project(root, monkeypatch)
    monkeypatch.chdir(root)
    workspace = workspace or root / "workspace"
    source = workspace / "state/control_plane_records.sqlite3"
    with monkeypatch.context() as old_layout:
        # These injected placement/scope inputs model the previous contract. They
        # do not replace authorization, execution, persistence or publication.
        for module in (
            "orket.orchestration.engine_services",
            "orket.application.workflows.orchestrator",
            "orket.application.workflows.orchestrator_ops",
        ):
            old_layout.setattr(module + ".control_plane_db_for_runtime", lambda **_: source)
        async with bound_engine(root, workspace, old_layout) as engine:
            engine._pipeline.epic_publication.storage_binding = None
            engine._pipeline.epic_publication.scope["runtime_db"] = "state/cards.db"
            approval = await pause(engine)
    return approval, migration(root, source)


def migration(root, source=None):
    return RuntimeStoreMigrationService(
        root / "state/cards.db",
        legacy_control_plane_db=source or root / "workspace/state/control_plane_records.sqlite3",
        legacy_invocation_root=root,
    )


def _copy_and_restore(paths: tuple[Path, ...], directory: Path):
    """Offloaded fixture helper: restore real SQLite backups at the original paths."""
    directory.mkdir()
    for index, path in enumerate(paths):
        archive, restored = directory / f"store-{index}.sqlite3", path.with_name(path.name + ".restored")
        with closing(sqlite3.connect(path)) as original, closing(sqlite3.connect(archive)) as backup:
            original.backup(backup)
        with closing(sqlite3.connect(archive)) as backup, closing(sqlite3.connect(restored)) as copied:
            backup.backup(copied)
        restored.replace(path)


async def copied_history(root, service):
    await asyncio.to_thread(
        _copy_and_restore,
        (service.binding.runtime_db, service.binding.repository.journal_db, service.source),
        root / "copied-history",
    )


async def retained_request(root):
    repository = SQLiteEpicPublicationRepository(root / "state/cards.db")
    async with repository.transaction("approval-session") as transaction:
        return (await transaction.get_admission()).request
