"""Retained source history and native ownership must survive store cutover."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.epic_continuation_lock import EpicContinuationLocks
from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.core.contracts.control_plane_models import ResolvedConfigurationSnapshot, RunRecord
from orket.core.contracts.epic_approval_recovery import EPIC_CONTINUATION_LOCK_ARTIFACT
from tests.helpers.runtime_store_migration import legacy_pause

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def add_foreign_run(source):
    async with aiosqlite.connect(source) as conn:
        row = await (await conn.execute("SELECT payload_json FROM control_plane_runs LIMIT 1")).fetchone()
        run = RunRecord.model_validate_json(row[0])
        row = await (
            await conn.execute(
                "SELECT payload_json FROM resolved_configuration_snapshots WHERE snapshot_id=?",
                (run.configuration_snapshot_id,),
            )
        ).fetchone()
        config = ResolvedConfigurationSnapshot.model_validate_json(row[0])
        payload = {**config.configuration_payload, "session_id": "another-runtime-session"}
        config = config.model_copy(
            update={
                "snapshot_id": "foreign-config",
                "configuration_payload": payload,
                "snapshot_digest": snapshot_digest(payload),
            }
        )
        run = run.model_copy(
            update={
                "run_id": "foreign-run",
                "configuration_snapshot_id": config.snapshot_id,
                "configuration_digest": config.snapshot_digest,
            }
        )
        await conn.execute("INSERT INTO control_plane_runs VALUES (?, ?)", (run.run_id, run.model_dump_json()))
        await conn.execute(
            "INSERT INTO resolved_configuration_snapshots VALUES (?, ?, ?)",
            (config.snapshot_id, config.created_at, config.model_dump_json()),
        )
        await conn.commit()


@pytest.mark.parametrize("damage", ["orphan", "active", "foreign"])
# Layer: integration
async def test_migration_refuses_incomplete_or_mixed_source_history(tmp_path, monkeypatch, damage):
    _, service = await legacy_pause(tmp_path / "project", monkeypatch)
    if damage == "foreign":
        await add_foreign_run(service.source)
    else:
        table = "epic_run_admissions" if damage == "orphan" else "epic_approval_pauses"
        async with aiosqlite.connect(service.binding.repository.journal_db) as conn:
            await conn.execute("DELETE FROM " + table)
            await conn.commit()
    before = await service.io.snapshot_digest(service.binding.runtime_db)
    error = {"orphan": "ADMISSION_HISTORY_MISSING", "active": "ACTIVE_OWNER_UNRESOLVED", "foreign": "MIXED_AUTHORITY"}[
        damage
    ]
    with pytest.raises(ValueError, match=error):
        await service.migrate(actor_ref="acceptance:history", owners_stopped=True)
    assert await service.io.snapshot_digest(service.binding.runtime_db) == before
    assert not await asyncio.to_thread(service.binding.control_plane_db.exists)


# Layer: integration
async def test_migration_cannot_replace_a_claimed_pause_native_identity(tmp_path, monkeypatch):
    _, service = await legacy_pause(tmp_path / "project", monkeypatch)
    journal = service.binding.repository.journal_db
    async with (
        EpicContinuationLocks(journal).hold("approval-session") as lock,
        SQLiteEpicPublicationRepository(service.binding.runtime_db).transaction("approval-session") as tx,
    ):
        pause = await tx.approval_pauses.latest()
        claimed = pause.model_copy(
            update={
                "phase": "claimed",
                "decisions": {key: "approved" for key in pause.approvals},
                "artifacts": {**pause.artifacts, EPIC_CONTINUATION_LOCK_ARTIFACT: lock.model_dump(mode="json")},
            }
        )
        await tx.approval_pauses.save(claimed)
    path = Path(lock.lock_path)
    await asyncio.to_thread(path.rename, path.with_suffix(".preserved"))
    with pytest.raises(ValueError, match="CONTINUATION_LOCK_CHANGED"):
        await service.migrate(actor_ref="acceptance:lock", owners_stopped=True)
    assert await service.binding.repository.read_binding(service.binding.runtime_db) is None
    assert not await asyncio.to_thread(service.binding.control_plane_db.exists)
