"""Migration admission and native file-publication boundaries."""

from __future__ import annotations

import asyncio
import os

import aiosqlite
import pytest

from orket.application.services.runtime_store_migration_service import RuntimeStoreMigrationService
from tests.helpers.runtime_store_migration import legacy_pause, migration
from tests.integration.test_runtime_store_binding import bound_engine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("mistake", ["offline", "invocation", "target_record"])
# Layer: integration
async def test_migration_requires_stopped_owners_and_original_authority(tmp_path, monkeypatch, mistake):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch)
    if mistake == "invocation":
        service = RuntimeStoreMigrationService(
            service.binding.runtime_db, legacy_control_plane_db=service.source, legacy_invocation_root=root / "other"
        )
    elif mistake == "target_record":
        async with aiosqlite.connect(service.source) as conn:
            await conn.execute("DELETE FROM control_plane_runs WHERE run_id=?", (approval["control_plane_target_ref"],))
            await conn.commit()
    before = await service.io.snapshot_digest(service.binding.runtime_db)
    error = {
        "offline": "OFFLINE_REQUIRED",
        "invocation": "SOURCE_BINDING_CONFLICT",
        "target_record": "APPROVAL_TARGET_MISSING",
    }[mistake]
    with pytest.raises(ValueError, match=error):
        await service.migrate(actor_ref="acceptance:refusal", owners_stopped=mistake != "offline")
    assert await service.io.snapshot_digest(service.binding.runtime_db) == before
    assert not await asyncio.to_thread(service.binding.control_plane_db.exists)


# Layer: integration
async def test_target_created_after_preflight_is_preserved(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    publish = service.io.publish

    async def competing_target(staging, target):
        await asyncio.to_thread(target.write_bytes, b"other operator's file")
        await publish(staging, target)

    monkeypatch.setattr(service.io, "publish", competing_target)
    with pytest.raises(FileExistsError):
        await service.migrate(actor_ref="acceptance:race", owners_stopped=True)
    assert await asyncio.to_thread(service.binding.control_plane_db.read_bytes) == b"other operator's file"
    assert await service.binding.repository.read_binding(service.binding.runtime_db) is not None


# Layer: integration
async def test_restart_finishes_cleanup_after_exclusive_publication(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    from orket.adapters.storage import runtime_store_migration_io

    publish = runtime_store_migration_io._publish

    def interrupted_after_link(staging, target):
        os.link(staging, target)
        raise OSError("controlled interruption after publication")

    monkeypatch.setattr(runtime_store_migration_io, "_publish", interrupted_after_link)
    with pytest.raises(OSError, match="after publication"):
        await service.migrate(actor_ref="acceptance:published", owners_stopped=True)
    monkeypatch.setattr(runtime_store_migration_io, "_publish", publish)
    binding = await migration(root).migrate(actor_ref="acceptance:retry", owners_stopped=True)
    await service.binding.initialize()
    assert binding == await service.binding.repository.read_binding(service.binding.control_plane_db)
    assert not await asyncio.to_thread(
        service.binding.control_plane_db.with_name("control_plane_records.sqlite3.binding-staging.sqlite3").exists
    )


# Layer: integration
async def test_already_colocated_history_binds_without_copying_the_control_plane(tmp_path, monkeypatch):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch, workspace=root)
    before = await service.io.snapshot_digest(service.source)
    binding = await service.migrate(actor_ref="acceptance:colocated", owners_stopped=True)
    assert service.source == service.binding.control_plane_db
    assert await service.io.snapshot_digest(service.source) == before
    async with bound_engine(root, root, monkeypatch) as engine:
        response = await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
        assert response["runtime_result"]["succeeded"]
    assert await service.migrate(actor_ref="acceptance:repeat", owners_stopped=True) == binding
