from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace

import aiosqlite

from orket.adapters.storage.outward_run_event_store import _MIGRATIONS as EVENT_MIGRATIONS
from orket.adapters.storage.outward_run_store import _MIGRATIONS as RUN_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.domain.outward_ledger import (
    GENESIS_CHAIN_HASH,
    canonical_event,
    chain_hash_for,
    event_hash_for,
    event_order_key,
)
from tests.helpers.outward_ledger import ledger_event


async def seed_legacy_ledger(path, count=4, *, unsealed=False):
    events = sorted((replace(ledger_event(i), run_id="legacy", event_id=f"legacy:{i:06d}",
                             turn=None if i == 1 else i % 3) for i in range(1, count + 1)), key=event_order_key)
    chain, records, exported = GENESIS_CHAIN_HASH, [], []
    for position, event in enumerate(events, start=1):
        digest, previous = event_hash_for(event), chain
        chain = chain_hash_for(chain, digest)
        records.append((event.event_id, event.event_type, event.run_id, event.turn, event.agent_id,
                        event.at, json.dumps(event.payload), None if unsealed else digest, None if unsealed else chain))
        exported.append({**canonical_event(event), "position": position, "event_hash": digest,
                         "previous_chain_hash": previous, "chain_hash": chain})
    async with aiosqlite.connect(path) as connection:
        await SQLiteMigrationRunner(namespace="outward_runs").apply(connection, RUN_MIGRATIONS[:1])
        await SQLiteMigrationRunner(namespace="outward_run_events").apply(connection, EVENT_MIGRATIONS[:1])
        await connection.execute("""INSERT INTO outward_runs (
            run_id, status, namespace, submitted_at, current_turn, max_turns,
            task_json, policy_overrides_json, pending_proposals_json
        ) VALUES ('legacy', 'approval_required', 'local', '2026-09-12T12:00:00+00:00', 1, 1, '{}', '{}', '[]')""")
        await connection.executemany("INSERT INTO run_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", records)
        await connection.commit()
    return {
        "schema_version": "ledger_export.v1", "run_id": "legacy", "export_scope": "all",
        "canonical": {"ordering": ["run_id", "turn", "at", "event_id"], "genesis": GENESIS_CHAIN_HASH,
                      "event_count": count, "ledger_hash": chain}, "events": exported, "omitted_spans": [],
    }


async def table_rows(path, table):
    assert table in {"run_events", "outward_runs", "outward_ledger_heads_v2", "outward_ledger_commits_v2"}
    async with aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        return await (await connection.execute(f"SELECT * FROM {table} ORDER BY 1")).fetchall()


async def migration_cli(source, backup, destination, report, *options):
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "scripts.governance.migrate_outward_ledger", "--source", str(source),
        "--backup", str(backup), "--destination", str(destination), "--out", str(report), *options,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    return process.returncode, stdout.decode(), stderr.decode()
