from __future__ import annotations

import sqlite3

import aiosqlite

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


def ledger_event(position: int) -> LedgerEvent:
    return LedgerEvent(
        event_id=f"bt2:{position:06d}", event_type="tool_invoked", run_id="bt2",
        turn=1, agent_id="bt2-fixture", at="2026-09-12T12:00:00+00:00",
        payload={"position": position, "outcome": "success"},
    )


async def seed_ledger(db_path, count: int) -> OutwardLedgerService:
    runs, events = OutwardRunStore(db_path), OutwardRunEventStore(db_path)
    await runs.create(OutwardRunRecord(
        run_id="bt2", status="completed", namespace="local",
        submitted_at="2026-09-12T12:00:00+00:00", current_turn=1, max_turns=1,
        task={}, policy_overrides={}, execution_generation=1,
    ))
    await events.ensure_initialized()
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute("BEGIN IMMEDIATE")
        for position in range(1, count + 1):
            await events.append(ledger_event(position), connection=connection)
        await connection.commit()
    return OutwardLedgerService(
        run_store=runs, event_store=events, utc_now=lambda: "2026-09-12T12:01:00+00:00",
    )


def logical_contents(db_path) -> tuple[str, ...]:
    # A read-only independent connection observes every retained table and schema.
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as connection:
        return tuple(connection.iterdump())


async def event_count(db_path) -> int:
    async with aiosqlite.connect(db_path) as connection:
        row = await (await connection.execute("SELECT COUNT(*) FROM run_events WHERE run_id='bt2'")).fetchone()
    return int(row[0])


async def allow_at_rest_corruption(connection) -> None:
    """Model an actor who can alter the database itself, beyond the normal writer guards."""
    rows = await (await connection.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='run_events'",
    )).fetchall()
    assert len(rows) == 3, "expected the native event write/update/delete guards"
    for row in rows:
        quoted = str(row[0]).replace('"', '""')
        await connection.execute(f'DROP TRIGGER "{quoted}"')
