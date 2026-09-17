from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from tests.helpers.outward_ledger import allow_at_rest_corruption, event_count, logical_contents, seed_ledger


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Real append must commit evidence without a subsequent read repair.
async def test_event_commitment_exists_before_first_verification(tmp_path) -> None:
    db_path = tmp_path / "append.sqlite3"
    service = await seed_ledger(db_path, 1)
    event = await service.event_store.get("bt2:000001")
    assert event is not None and event.event_hash, "append left the event uncommitted"
    before = await asyncio.to_thread(logical_contents, db_path)
    assert (await service.verify_run("bt2"))["result"] == "valid"
    assert (await service.verify_run("bt2"))["result"] == "valid"
    assert await asyncio.to_thread(logical_contents, db_path) == before


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["payload", "event_hash", "chain_hash", "order", "middle", "tail"])
# Layer: integration. Tamper with the real database, then verify twice without resealing it.
async def test_retained_corruption_is_rejected_without_repair(tmp_path, mutation: str) -> None:
    db_path = tmp_path / "corrupt.sqlite3"
    service = await seed_ledger(db_path, 3)
    assert (await service.verify_run("bt2"))["result"] == "valid"
    statements = {
        "payload": "UPDATE run_events SET payload_json='{}' WHERE event_id='bt2:000002'",
        "event_hash": "UPDATE run_events SET event_hash='corrupt' WHERE event_id='bt2:000002'",
        "chain_hash": "UPDATE run_events SET chain_hash='corrupt' WHERE event_id='bt2:000002'",
        "order": "UPDATE run_events SET turn=0 WHERE event_id='bt2:000002'",
        "middle": "DELETE FROM run_events WHERE event_id='bt2:000002'",
        "tail": "DELETE FROM run_events WHERE event_id='bt2:000003'",
    }
    async with aiosqlite.connect(db_path) as connection:
        await allow_at_rest_corruption(connection)
        await connection.execute(statements[mutation])
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, db_path)
    reports = [await service.verify_run("bt2"), await service.verify_run("bt2")]
    after = await asyncio.to_thread(logical_contents, db_path)
    assert after == before, "verification changed the retained database"
    assert [report["result"] for report in reports] == ["invalid", "invalid"]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, 4999, 5000, 5001])
# Layer: integration. Seed via the real store; query count independently of returned rows.
async def test_full_export_includes_independently_counted_snapshot_tail(tmp_path, count: int) -> None:
    db_path = tmp_path / "complete.sqlite3"
    service = await seed_ledger(db_path, count)
    exported = await service.export("bt2")
    retained_count = await event_count(db_path)
    assert retained_count == count
    assert exported["canonical"]["event_count"] == retained_count
    assert len(exported["events"]) == retained_count
    assert exported["verification"]["result"] == "valid"
    if count:
        assert exported["events"][-1]["event_id"] == f"bt2:{count:06d}"


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Each real PII export must retain and disclose its own audit event.
async def test_repeated_pii_exports_include_distinct_audits_above_old_cap(tmp_path) -> None:
    db_path = tmp_path / "audit.sqlite3"
    service = await seed_ledger(db_path, 5000)
    exports = [
        await service.export("bt2", include_pii=True, record_request=True, operator_ref=f"operator:{number}")
        for number in range(2)
    ]
    assert await event_count(db_path) == 5002
    for number, exported in enumerate(exports):
        assert exported["canonical"]["event_count"] == 5001 + number
        audits = [event for event in exported["events"] if event["event_type"] == "ledger_export_requested"]
        assert len(audits) == number + 1
        assert any(event["payload"]["operator_ref"] == f"operator:{number}" for event in audits)
