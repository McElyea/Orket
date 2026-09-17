from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import aiosqlite
import pytest

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_ledger_upgrade import migrate_outward_ledger_copy
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.core.domain.outward_ledger import MAX_LEDGER_EXPORT_EVENTS, MAX_LEDGER_PAYLOAD_BYTES
from orket.core.domain.outward_ledger_integrity import OutwardLedgerIntegrityError
from tests.helpers.outward_ledger import ledger_event
from tests.helpers.outward_ledger_migration import seed_legacy_ledger


async def _seed_limit(path, limit):
    await seed_legacy_ledger(path, count=1, unsealed=True)
    async with aiosqlite.connect(path) as connection:
        if limit == "event_count":
            await connection.execute("""WITH RECURSIVE positions(i) AS (
                SELECT 2 UNION ALL SELECT i+1 FROM positions WHERE i<?
            ) INSERT INTO run_events
            SELECT printf('limit:%06d', i), 'tool_invoked', 'legacy', 1, NULL, 'retained', '{}', NULL, NULL
            FROM positions""", (MAX_LEDGER_EXPORT_EVENTS,))
        else:
            payload = json.dumps({"blob": "x" * (MAX_LEDGER_PAYLOAD_BYTES - len('{"blob":""}'))}, separators=(",", ":"))
            assert len(payload.encode()) == MAX_LEDGER_PAYLOAD_BYTES
            await connection.execute("UPDATE run_events SET payload_json=?", (payload,))
        await connection.commit()


async def _one_over_limit(path, limit):
    async with aiosqlite.connect(path) as connection:
        if limit == "event_count":
            await connection.execute("""INSERT INTO run_events VALUES (
                'overflow', 'tool_invoked', 'legacy', 1, NULL, 'retained', '{}', NULL, NULL)""")
        else:
            await connection.execute("UPDATE run_events SET payload_json=payload_json || ' '")
        await connection.commit()


@pytest.mark.integration
@pytest.mark.parametrize("limit", ["event_count", "payload_bytes"])
# Layer: integration. Exercise the actual 100,000-event and 64 MiB limits, including exactly accepted and one over.
async def test_actual_migration_and_snapshot_resource_boundaries(tmp_path, limit):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await _seed_limit(source, limit)
    report = await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination,
                                              writers_stopped=True, allow_unsealed=True)
    expected_count = MAX_LEDGER_EXPORT_EVENTS if limit == "event_count" else 1
    assert report["runs"][0]["event_count"] == expected_count
    snapshot = await OutwardLedgerSnapshotStore(destination).read("legacy")
    assert snapshot.independent_count == expected_count and len(snapshot.events) == expected_count
    del snapshot
    await OutwardRunEventStore(destination).append(replace(ledger_event(0), run_id="legacy", event_id="overflow"))
    with pytest.raises(OutwardLedgerIntegrityError, match="SNAPSHOT_RESOURCE_LIMIT") as error:
        await OutwardLedgerSnapshotStore(destination).read("legacy")
    assert error.value.category == "resource"
    await _one_over_limit(source, limit)
    rejected = tmp_path / "rejected.db"
    with pytest.raises(OutwardLedgerIntegrityError, match="SNAPSHOT_RESOURCE_LIMIT"):
        await migrate_outward_ledger_copy(source=source, backup=tmp_path / "overflow-backup.db", destination=rejected,
                                          writers_stopped=True, allow_unsealed=True)
    async with aiosqlite.connect(rejected.as_uri() + "?mode=ro", uri=True) as connection:
        assert await (await connection.execute(
            "SELECT name FROM sqlite_master WHERE name='outward_ledger_heads_v2'",
        )).fetchone() is None
    assert await asyncio.to_thread(backup.is_file)
