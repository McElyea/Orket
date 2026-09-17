"""Layer: integration. Real legacy SQLite copies and the offline migration command."""

from __future__ import annotations

import asyncio
import json
import sys

import aiosqlite
import pytest

from orket.adapters.storage.outward_approval_migrations import OUTWARD_APPROVAL_MIGRATIONS
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_approval_upgrade import migrate_outward_approval_copy
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from tests.helpers.outward_authorization import TEST_API_KEY, FixedInputs, approve, outward_api


async def seed_legacy(path):
    async with connect_sqlite_wal(path) as conn:
        await SQLiteMigrationRunner(namespace="outward_approvals").apply(conn, OUTWARD_APPROVAL_MIGRATIONS[:1])
        for state in ("pending", "approved", "denied"):
            await conn.execute("""INSERT INTO outward_approval_proposals (
                proposal_id, run_id, namespace, tool, args_preview_json, context_summary,
                risk_level, submitted_at, expires_at, status, operator_ref, decision
            ) VALUES (?, 'legacy-run', 'legacy', 'write_file', '{}', 'old history', 'write',
                '2026-09-11T12:00:00+00:00', '2099-09-11T12:00:00+00:00', ?, 'operator:old', ?)""",
                ("legacy:" + state, state, "approve" if state == "approved" else "deny" if state == "denied" else None))
        await conn.commit()


@pytest.mark.integration
# Layer: integration
async def test_populated_legacy_store_requires_offline_copy_and_retains_history(tmp_path):
    """Layer: integration. Startup refuses automatic old-row promotion; the CLI upgrades only a copied store."""
    source, backup, destination = [tmp_path / name for name in ("source.sqlite3", "backup.sqlite3", "new.sqlite3")]
    await seed_legacy(source)
    with pytest.raises(RuntimeError, match="E_OUTWARD_OFFLINE_APPROVAL_MIGRATION_REQUIRED"):
        await OutwardApprovalStore(source).ensure_initialized()
    report = tmp_path / "migration.json"
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "scripts.governance.migrate_outward_approvals", "--source", str(source),
        "--backup", str(backup), "--destination", str(destination), "--writers-stopped", "--out", str(report),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == 0, stderr.decode()
    payload = json.loads(report.read_text())
    assert payload["unbound_legacy_proposals_by_status"] == {"approved": 1, "denied": 1, "pending": 1}
    assert payload["legacy_dispatch_enabled"] is False and payload["diff_ledger"]
    for path in (source, backup):
        async with connect_sqlite_wal(path) as conn:
            cursor = await conn.execute("SELECT status FROM outward_approval_proposals ORDER BY status")
            assert [row[0] for row in await cursor.fetchall()] == ["approved", "denied", "pending"]
    store = OutwardApprovalStore(destination)
    for status in ("approved", "denied", "pending"):
        proposal = await store.get("legacy:" + status)
        assert proposal.status == status and proposal.operator_ref == "operator:old"
        assert proposal.authorization is None
    async with connect_sqlite_wal(destination) as conn:
        with pytest.raises(aiosqlite.OperationalError, match="no such table"):
            await conn.execute("SELECT * FROM outward_approval_proposals")
        with pytest.raises(aiosqlite.OperationalError, match="no such table"):
            await conn.execute("UPDATE outward_approval_proposals SET status = 'approved'")


@pytest.mark.integration
# Layer: integration
async def test_offline_migration_refuses_live_writers_and_overwrites(tmp_path):
    """Layer: integration. Missing shutdown acknowledgement and reused destinations fail before copying."""
    source, backup, destination = [tmp_path / name for name in ("source.sqlite3", "backup.sqlite3", "new.sqlite3")]
    await seed_legacy(source)
    with pytest.raises(ValueError, match="E_OUTWARD_WRITERS_MUST_BE_STOPPED"):
        await migrate_outward_approval_copy(source=source, backup=backup, destination=destination, writers_stopped=False)
    assert not backup.exists() and not destination.exists()
    destination.write_text("preserve")
    with pytest.raises(FileExistsError):
        await migrate_outward_approval_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    assert destination.read_text() == "preserve" and not backup.exists()


@pytest.mark.integration
# Layer: integration
async def test_migrated_approved_history_cannot_authorize_a_current_model_call(tmp_path, monkeypatch):
    """Layer: integration. An authenticated legacy retry refuses to reconstruct its lost binding."""
    source, backup, destination = [tmp_path / name for name in ("source.sqlite3", "backup.sqlite3", "new.sqlite3")]
    await seed_legacy(source)
    await migrate_outward_approval_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(destination))
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    async with outward_api(tmp_path, FixedInputs()) as (client, context):
        await context.outward_run_service.submit({
            "run_id": "legacy-run", "task": {"description": "legacy", "instruction": "legacy"},
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        })
        response = await approve(client, "legacy:approved")
        assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_AUTHORIZATION_REQUIRED"
        pending = await approve(client, "legacy:pending")
        assert pending.status_code == 409 and pending.json()["detail"] == "E_OUTWARD_AUTHORIZATION_REQUIRED"
        assert (await context.outward_approval_store.get("legacy:approved")).operator_ref == "operator:old"
        events = await context.outward_run_event_store.list_for_run("legacy-run")
        assert not any(event.event_type == "tool_invoked" for event in events)
