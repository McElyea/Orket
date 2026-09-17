"""Initial outward admission owns its namespace and event in one real transaction."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import aiosqlite
import pytest

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import outward_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def submission(run_id):
    return {
        "run_id": run_id,
        "namespace": "issue:one-owner",
        "task": {"description": "atomic admission", "instruction": "wait for an explicit workload"},
    }


async def initialize_stores(context):
    for store in (context.outward_run_store, context.outward_run_event_store, context.outward_approval_store):
        await store.ensure_initialized()


@asynccontextmanager
async def competing_writers(db_path, monkeypatch):
    """Observe actual write attempts while a separate SQLite owner prevents writes."""
    ready, connections = asyncio.Event(), set()
    original = aiosqlite.Connection.execute

    def observe(connection, sql, *args, **kwargs):
        normalized = " ".join(sql.upper().split())
        if normalized == "BEGIN IMMEDIATE" or normalized.startswith("INSERT INTO OUTWARD_RUNS"):
            connections.add(id(connection))
            if len(connections) == 2:
                ready.set()
        return original(connection, sql, *args, **kwargs)

    async with connect_sqlite_wal(db_path) as owner:
        await owner.execute("BEGIN IMMEDIATE")
        try:
            with monkeypatch.context() as patch:
                patch.setattr(aiosqlite.Connection, "execute", observe)
                yield ready
        finally:
            await owner.rollback()


@pytest.mark.parametrize("fault", ["event", "ledger_head"])
# Layer: integration
async def test_initial_admission_rolls_back_when_event_publication_fails(tmp_path, boundary, fault):
    db_path, inputs, _ = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        await initialize_stores(context)
        target = "run_events" if fault == "event" else "outward_ledger_heads_v2"
        async with connect_sqlite_wal(db_path) as conn:
            await conn.execute(
                f"CREATE TRIGGER admission_abort BEFORE INSERT ON {target} "
                "BEGIN SELECT RAISE(ABORT, 'admission publication interrupted'); END"
            )
            await conn.commit()
        response = await client.post("/v1/runs", json=submission("admit-once"))
        assert response.status_code == 500
        assert await context.outward_run_store.get("admit-once") is None
        assert await context.outward_run_event_store.list_for_run("admit-once") == []
        async with connect_sqlite_wal(db_path) as conn:
            await conn.execute("DROP TRIGGER admission_abort")
            await conn.commit()
        retried = await client.post("/v1/runs", json=submission("admit-once"))
        assert retried.status_code == 200, retried.text
        events = await context.outward_run_event_store.list_for_run("admit-once")
        assert [event.event_type for event in events] == ["run_submitted"]


# Layer: integration
async def test_unrecorded_prior_admission_is_not_reconstructed_on_retry(tmp_path, boundary):
    _, inputs, _ = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        orphan = OutwardRunRecord(
            run_id="orphan",
            status="queued",
            namespace="issue:one-owner",
            submitted_at=inputs.utc_now_iso(),
            current_turn=0,
            max_turns=20,
            task=submission("orphan")["task"],
            policy_overrides={},
            execution_generation=1,
        )
        await context.outward_run_store.create(orphan)
        response = await client.post("/v1/runs", json=submission("orphan"))
        assert response.status_code == 409, response.text
        assert "E_OUTWARD_ADMISSION_EVENT_MISSING" in response.text
        assert await context.outward_run_store.get("orphan") == orphan
        assert await context.outward_run_event_store.list_for_run("orphan") == []


@pytest.mark.parametrize("same_id", [False, True])
# Layer: integration
async def test_competing_applications_admit_one_namespace_owner(tmp_path, boundary, monkeypatch, same_id):
    db_path, inputs, _ = boundary
    async with (
        outward_api(tmp_path, inputs) as (first, first_context),
        outward_api(tmp_path, inputs) as (second, second_context),
    ):
        await initialize_stores(first_context)
        await initialize_stores(second_context)
        tasks = []
        try:
            async with competing_writers(db_path, monkeypatch) as waiting:
                tasks = [
                    asyncio.create_task(first.post("/v1/runs", json=submission("first"))),
                    asyncio.create_task(second.post("/v1/runs", json=submission("first" if same_id else "second"))),
                ]
                await asyncio.wait_for(waiting.wait(), 4)
            responses = await asyncio.wait_for(asyncio.gather(*tasks), 10)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        assert sorted(response.status_code for response in responses) == ([200, 200] if same_id else [200, 409])
        runs = await first_context.outward_run_store.list()
        assert len(runs) == 1 and runs[0].status == "queued"
        events = await second_context.outward_run_event_store.list_for_run(runs[0].run_id)
        assert [event.event_type for event in events] == ["run_submitted"]
