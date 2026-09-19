from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from tests.helpers.outward_ledger import ledger_event, logical_contents, seed_ledger


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["event_hash", "chain", "sequence", "head", "count", "orphan", "origin"])
# Layer: integration. Alter real commitment/head metadata independently of the canonical event rows.
async def test_corrupt_retained_commitments_fail_without_repair(tmp_path, mutation) -> None:
    db_path = tmp_path / "commitments.sqlite3"
    service = await seed_ledger(db_path, 3)
    statements = {
        "event_hash": "UPDATE outward_ledger_commits_v2 SET event_hash='corrupt' WHERE append_sequence=2",
        "chain": "UPDATE outward_ledger_commits_v2 SET chain_hash='corrupt' WHERE append_sequence=2",
        "sequence": "UPDATE outward_ledger_commits_v2 SET append_sequence=99 WHERE append_sequence=2",
        "head": "UPDATE outward_ledger_heads_v2 SET chain_hash='" + "0" * 64 + "'",
        "count": "UPDATE outward_ledger_heads_v2 SET event_count=2",
        "orphan": "UPDATE outward_ledger_commits_v2 SET event_id='missing-event' WHERE append_sequence=2",
        "origin": "UPDATE outward_ledger_heads_v2 SET origin_ref='legacy:" + "0" * 64 + "'",
    }
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute(statements[mutation])
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, db_path)
    for _ in range(2):
        report = await service.verify_run("bt2")
        assert report["result"] == "invalid" and report["errors"]
    assert await asyncio.to_thread(logical_contents, db_path) == before


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration. Mutation of a caller-owned dict during real SQLite I/O cannot split hash from payload.
async def test_append_captures_payload_before_awaiting_commitment_write(tmp_path, monkeypatch) -> None:
    service = await seed_ledger(tmp_path / "captured.sqlite3", 0)
    event = ledger_event(1)
    reached, release = asyncio.Event(), asyncio.Event()
    original = aiosqlite.Connection._execute

    async def pause(connection, operation, *args, **kwargs):
        # Keep execute's awaitable/context-manager protocol intact; hold actual I/O.
        result = await original(connection, operation, *args, **kwargs)
        if args and isinstance(args[0], str) and args[0].startswith("INSERT INTO outward_ledger_commits_v2"):
            reached.set()
            await asyncio.wait_for(release.wait(), timeout=10)
        return result

    monkeypatch.setattr(aiosqlite.Connection, "_execute", pause)
    task = asyncio.create_task(service.event_store.append(event))
    try:
        await asyncio.wait_for(reached.wait(), timeout=10)
        event.payload["position"] = 999
    finally:
        release.set()
        await asyncio.wait_for(task, timeout=10)
    stored = await service.event_store.get(event.event_id)
    assert stored.payload["position"] == 1
    assert (await service.verify_run("bt2"))["result"] == "valid"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["run", "future", "schema", "hash", "boolean_count", "extra"])
# Layer: integration. Reject malformed/wrong anchors without mislabeling a valid local snapshot as corrupt.
async def test_external_anchor_validation_preserves_local_integrity_claim(tmp_path, mutation) -> None:
    db_path = tmp_path / "external.sqlite3"
    service = await seed_ledger(db_path, 3)
    anchor = (await service.export("bt2"))["retained"]["anchor"]
    fields = {
        "run": ("run_id", "another-run"), "future": ("event_count", 4),
        "schema": ("schema_version", "unknown"), "hash": ("chain_hash", []),
        "boolean_count": ("event_count", True), "extra": ("unrecognized", True),
    }
    field, value = fields[mutation]
    anchor[field] = value
    before = await asyncio.to_thread(logical_contents, db_path)
    report = await service.verify_run("bt2", external_anchor=anchor)
    assert report["result"] == report["external_anchor"] == "invalid"
    assert report["retained_integrity"] == report["snapshot_completeness"] == "valid"
    assert await asyncio.to_thread(logical_contents, db_path) == before
