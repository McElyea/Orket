"""Layer: integration. Reopen retained generation-1 claims through the versioned effect-store upgrade."""

from __future__ import annotations

from dataclasses import asdict

import aiosqlite
import pytest

from orket.adapters.storage.outward_effect_migrations import OUTWARD_EFFECT_MIGRATIONS
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from tests.helpers.outward_authorization import append_command, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import paused_effect_worker


async def copied_v1_claim(source, destination, effect):
    """Copy actual retained history, then represent its claim with the canonical original effect schema."""
    async with aiosqlite.connect(source) as reader, aiosqlite.connect(destination) as writer:
        await reader.backup(writer)
    async with connect_sqlite_wal(destination) as conn:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute("DROP TABLE outward_effects")
        await conn.execute("DELETE FROM schema_migrations WHERE namespace = 'outward_effects'")
        await SQLiteMigrationRunner(namespace="outward_effects").apply(conn, OUTWARD_EFFECT_MIGRATIONS[:1])
        fields = asdict(effect)
        fields.pop("recovery_decision_id")
        await conn.execute(
            f"INSERT INTO outward_effects ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            tuple(fields.values()),
        )
        await conn.commit()


@pytest.mark.integration
@pytest.mark.parametrize("interrupt", [False, True])
# Layer: integration
async def test_effect_schema_upgrade_preserves_claim_and_rolls_back_interruption(tmp_path, boundary, monkeypatch, interrupt):
    """An actual API upgrade of a copied old claim retains history and never dispatches during failed migration."""
    source, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
    async with paused_effect_worker(tmp_path, proposal_id, "claim"):
        original, journal = await effect_snapshot(source, proposal_id)
    destination = tmp_path / "copied-v1.sqlite3"
    await copied_v1_claim(source, destination, original)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(destination))
    if interrupt:
        async with connect_sqlite_wal(destination) as conn:
            await conn.execute("""CREATE TRIGGER bt1_upgrade_abort BEFORE INSERT ON schema_migrations
                WHEN NEW.namespace = 'outward_effects' AND NEW.version = 2
                BEGIN SELECT RAISE(ABORT, 'effect migration interrupted'); END""")
            await conn.commit()
        async with outward_api(tmp_path, inputs) as (client, _context):
            response = await client.get(f"/v1/approvals/{proposal_id}/effect")
            assert response.status_code == 500
        async with connect_sqlite_wal(destination) as conn:
            cursor = await conn.execute("PRAGMA table_info(outward_effects)")
            assert "recovery_decision_id" not in {row[1] for row in await cursor.fetchall()}
            cursor = await conn.execute("SELECT owner_id, fencing_generation, journal_entry_id FROM outward_effects")
            assert await cursor.fetchone() == (original.owner_id, 1, original.journal_entry_id)
            await conn.execute("DROP TRIGGER bt1_upgrade_abort")
            await conn.commit()
        assert not (tmp_path / "effects.txt").exists()
    async with outward_api(tmp_path, inputs) as (client, _context):
        inspected = await client.get(f"/v1/approvals/{proposal_id}/effect")
        assert inspected.status_code == 200 and inspected.json()["fencing_generation"] == 1
        assert await effect_snapshot(destination, proposal_id) == (original, journal)
        response = await client.post(f"/v1/approvals/{proposal_id}/effect/recover", json={
            "request_id": "copied-claim-recovery", "expected_owner_id": original.owner_id, "expected_fencing_generation": 1,
        })
        assert response.status_code == 200 and response.json()["effect"]["fencing_generation"] == 2
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]
    assert await effect_snapshot(source, proposal_id) == (original, journal)
