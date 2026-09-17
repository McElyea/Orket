from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import aiosqlite
import pytest

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore, event_from_row
from orket.application.services.outward_ledger_service import OutwardLedgerValidationError
from orket.core.domain.outward_ledger import GENESIS_CHAIN_HASH, event_hash_for, verify_ledger_export
from orket.core.domain.outward_ledger_integrity import append_chain_hash
from tests.helpers.outward_ledger import (
    allow_at_rest_corruption,
    event_count,
    ledger_event,
    logical_contents,
    seed_ledger,
)


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. A second real WAL writer commits while the reader holds its snapshot.
async def test_export_snapshot_excludes_append_committed_between_pages(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "snapshot.sqlite3"
    service = await seed_ledger(db_path, 3)
    service.snapshot_store = OutwardLedgerSnapshotStore(db_path, page_size=2)
    reached, release = asyncio.Event(), asyncio.Event()
    original = service.snapshot_store._read_page

    async def pause(connection, run_id, after):
        rows = await original(connection, run_id, after)
        if after == 0:
            reached.set()
            await asyncio.wait_for(release.wait(), timeout=10)
        return rows

    monkeypatch.setattr(service.snapshot_store, "_read_page", pause)
    export_task = asyncio.create_task(service.export("bt2"))
    try:
        await asyncio.wait_for(reached.wait(), timeout=10)
        await OutwardRunEventStore(db_path).append(ledger_event(4))
        assert await event_count(db_path) == 4
    finally:
        release.set()
        exported = await asyncio.wait_for(export_task, timeout=10)
    assert exported["canonical"]["event_count"] == 3
    assert exported["retained"]["anchor"]["event_count"] == 3
    assert [event["event_id"] for event in exported["events"]] == [f"bt2:{i:06d}" for i in range(1, 4)]
    later = await service.export("bt2")
    assert later["canonical"]["event_count"] == 4
    assert verify_ledger_export(exported)["result"] == verify_ledger_export(later)["result"] == "valid"


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. A real SQLite failure at head publication cannot leave a partial append.
async def test_append_failure_rolls_back_event_commitment_and_head(tmp_path) -> None:
    db_path = tmp_path / "atomic.sqlite3"
    service = await seed_ledger(db_path, 1)
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute("""CREATE TRIGGER bt2_abort_head BEFORE UPDATE ON outward_ledger_heads_v2
            BEGIN SELECT RAISE(ABORT, 'bt2 head fault'); END""")
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, db_path)
    with pytest.raises(aiosqlite.IntegrityError, match="bt2 head fault"):
        await service.event_store.append(ledger_event(2))
    assert await asyncio.to_thread(logical_contents, db_path) == before
    assert (await service.verify_run("bt2"))["result"] == "valid"


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Retained append order stays stable even when v1 display order changes.
async def test_prior_external_anchor_survives_later_backdated_append(tmp_path) -> None:
    db_path = tmp_path / "anchor.sqlite3"
    service = await seed_ledger(db_path, 3)
    before = await service.export("bt2")
    anchor_path = tmp_path / "independently-retained-anchor.json"
    await asyncio.to_thread(anchor_path.write_text, json.dumps(before["retained"]["anchor"]), encoding="utf-8")
    await service.event_store.append(replace(ledger_event(4), turn=0))
    anchor = json.loads(await asyncio.to_thread(anchor_path.read_text, encoding="utf-8"))
    after = await service.export("bt2")
    assert after["events"][0]["event_id"] == "bt2:000004"
    assert after["canonical"]["ledger_hash"] != before["canonical"]["ledger_hash"]
    report = await service.verify_run("bt2", external_anchor=anchor)
    assert report["result"] == "valid" and report["external_anchor"] == "matched_prefix"
    assert report["authenticity"] == "not_established"


async def _rewrite_local_history(db_path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        connection.row_factory = aiosqlite.Row
        await connection.execute("BEGIN IMMEDIATE")
        await allow_at_rest_corruption(connection)
        await connection.execute("UPDATE run_events SET payload_json='{}' WHERE event_id='bt2:000001'")
        rows = await (await connection.execute("SELECT * FROM run_events ORDER BY event_id")).fetchall()
        previous = GENESIS_CHAIN_HASH
        for sequence, row in enumerate(rows, start=1):
            event = event_from_row(row)
            event = replace(event, event_hash=event_hash_for(event))
            chain = append_chain_hash(event, sequence, previous, "native")
            await connection.execute("UPDATE run_events SET event_hash=? WHERE event_id=?", (event.event_hash, event.event_id))
            await connection.execute(
                "UPDATE outward_ledger_commits_v2 SET event_hash=?, chain_hash=? WHERE event_id=?",
                (event.event_hash, chain, event.event_id),
            )
            previous = chain
        await connection.execute("UPDATE outward_ledger_heads_v2 SET chain_hash=? WHERE run_id='bt2'", (previous,))
        await connection.commit()


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. An attacker can reseal local storage, but cannot match a prior independent anchor.
async def test_external_anchor_detects_rewrite_of_all_local_commitments(tmp_path) -> None:
    db_path = tmp_path / "rewrite.sqlite3"
    service = await seed_ledger(db_path, 3)
    anchor = (await service.export("bt2"))["retained"]["anchor"]
    await _rewrite_local_history(db_path)
    before = await asyncio.to_thread(logical_contents, db_path)
    assert (await service.verify_run("bt2"))["result"] == "valid"
    report = await service.verify_run("bt2", external_anchor=anchor)
    assert report["result"] == "invalid" and report["external_anchor"] == "invalid"
    assert report["retained_integrity"] == report["snapshot_completeness"] == "valid"
    assert report["errors"] == ["E_OUTWARD_LEDGER_EXTERNAL_ANCHOR_MISMATCH"]
    assert await asyncio.to_thread(logical_contents, db_path) == before


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Verification/export cannot perform migration or manufacture a new empty store.
async def test_read_does_not_initialize_legacy_or_create_missing_database(tmp_path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    service = await seed_ledger(db_path, 1)
    async with aiosqlite.connect(db_path) as connection:
        await allow_at_rest_corruption(connection)
        await connection.execute("DROP TABLE outward_ledger_commits_v2")
        await connection.execute("DROP TABLE outward_ledger_heads_v2")
        await connection.execute("DELETE FROM schema_migrations WHERE namespace='outward_run_events' AND version=2")
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, db_path)
    assert (await service.verify_run("bt2"))["retained_integrity"] == "not_verified"
    with pytest.raises(OutwardLedgerValidationError, match="UNSEALED"):
        await service.export("bt2")
    assert await asyncio.to_thread(logical_contents, db_path) == before
    missing = tmp_path / "missing.sqlite3"
    reader = OutwardLedgerSnapshotStore(missing)
    with pytest.raises(ValueError, match="E_OUTWARD_LEDGER_STORAGE_READ"):
        await reader.read("bt2")
    assert not missing.exists()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["insert", "replace", "update", "delete"])
# Layer: integration. Execute real old-style SQL, including REPLACE's implicit deletion behavior.
async def test_old_event_writer_cannot_bypass_native_commitments(tmp_path, operation: str) -> None:
    db_path = tmp_path / "writer-guard.sqlite3"
    service = await seed_ledger(db_path, 1)
    event = await service.event_store.get("bt2:000001")
    statements = {
        "insert": "INSERT INTO run_events SELECT 'old-writer', event_type, run_id, turn, agent_id, at, payload_json, NULL, NULL FROM run_events",
        "replace": "INSERT OR REPLACE INTO run_events SELECT event_id, event_type, run_id, turn, agent_id, at, '{}', event_hash, chain_hash FROM run_events",
        "update": "UPDATE run_events SET chain_hash='old-reseal' WHERE event_id='bt2:000001'",
        "delete": "DELETE FROM run_events WHERE event_id='bt2:000001'",
    }
    before = await asyncio.to_thread(logical_contents, db_path)
    async with aiosqlite.connect(db_path) as connection:
        with pytest.raises(aiosqlite.IntegrityError, match="E_OUTWARD_LEDGER_"):
            await connection.execute(statements[operation])
        await connection.rollback()
    assert await service.event_store.get(event.event_id) == event
    assert await asyncio.to_thread(logical_contents, db_path) == before
