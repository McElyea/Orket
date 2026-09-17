"""Real migration, pause/restart and conflict proof under the declared legacy layout."""

from __future__ import annotations

import asyncio
import sqlite3

import aiosqlite
import pytest

from orket.adapters.storage.epic_continuation_lock import EpicContinuationLocks
from tests.helpers.runtime_store_migration import copied_history, legacy_pause, migration, retained_request
from tests.integration.test_runtime_store_binding import bound_engine

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("decision", ["approve", "deny"])
# Layer: integration
async def test_copied_relative_history_resumes_without_rewriting_request(tmp_path, monkeypatch, decision):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch)
    request = await retained_request(root)
    await copied_history(root, service)
    before = await service.io.snapshot_digest(service.source)
    binding = await service.migrate(actor_ref="acceptance:copy", owners_stopped=True)
    assert binding.sessions[0].session_id == "approval-session"
    assert await service.io.snapshot_digest(service.source) == before
    async with bound_engine(root, root / "workspace", monkeypatch) as engine:
        response = await engine.decide_approval(approval_id=approval["approval_id"], decision=decision)
        assert response["runtime_result"]["succeeded"] is (decision == "approve")
        again = await engine.decide_approval(approval_id=approval["approval_id"], decision=decision)
        assert again["status"] == "idempotent"
    assert await retained_request(root) == request
    assert await asyncio.to_thread((root / "workspace/agent_output/approved.txt").exists) is (decision == "approve")
    assert await migration(root).migrate(actor_ref="acceptance:repeat", owners_stopped=True) == binding


@pytest.mark.parametrize("absolute", [False, True])
# Layer: integration
async def test_unbound_history_refuses_approval_before_mutation(tmp_path, monkeypatch, absolute):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch)
    before = await service.io.snapshot_digest(service.binding.runtime_db)
    async with bound_engine(
        root, root / "workspace", monkeypatch, db_path=str(service.binding.runtime_db) if absolute else "state/cards.db"
    ) as engine:
        with pytest.raises(ValueError, match="E_RUNTIME_STORE_MIGRATION_REQUIRED"):
            await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
    assert await service.io.snapshot_digest(service.binding.runtime_db) == before
    assert not await asyncio.to_thread(service.binding.control_plane_db.exists)


# Layer: integration
async def test_interrupted_binding_refuses_then_completes_same_migration(tmp_path, monkeypatch):
    root = tmp_path / "project"
    approval, service = await legacy_pause(root, monkeypatch)

    async def interrupted(*_):
        raise OSError("controlled failure before publication")

    monkeypatch.setattr(service.io, "publish", interrupted)
    with pytest.raises(OSError, match="controlled failure"):
        await service.migrate(actor_ref="acceptance:interrupted", owners_stopped=True)
    async with bound_engine(root, root / "workspace", monkeypatch) as engine:
        with pytest.raises(ValueError, match="E_RUNTIME_STORE_BINDING_INCOMPLETE"):
            await engine.decide_approval(approval_id=approval["approval_id"], decision="approve")
    binding = await migration(root).migrate(actor_ref="acceptance:interrupted", owners_stopped=True)
    assert binding == await service.binding.repository.read_binding(service.binding.runtime_db)
    assert not await asyncio.to_thread(
        service.binding.control_plane_db.with_name("control_plane_records.sqlite3.binding-staging.sqlite3").exists
    )


# Layer: integration
async def test_unrelated_target_is_never_merged_or_replaced(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    target = service.binding.control_plane_db
    async with aiosqlite.connect(target) as conn:
        await conn.execute("CREATE TABLE unrelated (value TEXT)")
        await conn.execute("INSERT INTO unrelated VALUES ('keep this authority')")
        await conn.commit()
    before = await asyncio.to_thread(target.read_bytes)
    with pytest.raises(ValueError, match="E_RUNTIME_STORE_MIGRATION_TARGET_CONFLICT"):
        await service.migrate(actor_ref="acceptance:conflict", owners_stopped=True)
    assert await asyncio.to_thread(target.read_bytes) == before
    assert await service.binding.repository.read_binding(service.binding.runtime_db) is None


# Layer: integration
async def test_migration_copies_committed_wal_content(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    async with aiosqlite.connect(service.source) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA wal_autocheckpoint=0")
        await conn.execute("CREATE TABLE migration_wal_probe (value TEXT)")
        await conn.commit()
        before = await asyncio.to_thread(service.source.read_bytes)
        await conn.execute("INSERT INTO migration_wal_probe VALUES ('committed only in WAL')")
        await conn.commit()
        assert await asyncio.to_thread(service.source.read_bytes) == before
        await service.migrate(actor_ref="acceptance:wal", owners_stopped=True)
    async with aiosqlite.connect(service.binding.control_plane_db) as conn:
        cursor = await conn.execute("SELECT value FROM migration_wal_probe")
        assert await cursor.fetchall() == [("committed only in WAL",)]


@pytest.mark.parametrize("owner", ["sqlite", "continuation"])
# Layer: integration
async def test_active_owners_refuse_migration(tmp_path, monkeypatch, owner):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    if owner == "sqlite":
        async with aiosqlite.connect(service.source) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                await service.migrate(actor_ref="acceptance:busy", owners_stopped=True)
    else:
        async with EpicContinuationLocks(service.binding.repository.journal_db).hold("approval-session"):
            with pytest.raises(ValueError, match="owner_busy"):
                await service.migrate(actor_ref="acceptance:busy", owners_stopped=True)
    assert await service.binding.repository.read_binding(service.binding.runtime_db) is None
    assert not await asyncio.to_thread(service.binding.control_plane_db.exists)


# Layer: integration
async def test_cancelled_migration_retains_owned_publication_and_known_state(tmp_path, monkeypatch):
    root = tmp_path / "project"
    _, service = await legacy_pause(root, monkeypatch)
    entered, release = asyncio.Event(), asyncio.Event()
    publish = service.io.publish

    async def held_publish(staging, target):
        entered.set()
        await release.wait()
        await publish(staging, target)

    monkeypatch.setattr(service.io, "publish", held_publish)
    task = asyncio.create_task(service.migrate(actor_ref="acceptance:cancel", owners_stopped=True))
    await asyncio.wait_for(entered.wait(), 10)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await service.binding.initialize()
    assert await service.binding.repository.read_binding(
        service.binding.runtime_db
    ) == await service.binding.repository.read_binding(service.binding.control_plane_db)
