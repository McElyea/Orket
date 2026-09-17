"""Layer: integration. Copied legacy histories remain inert through authenticated reentry."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import timedelta

import pytest

from orket.adapters.storage.outward_approval_migrations import OUTWARD_APPROVAL_MIGRATIONS
from orket.adapters.storage.outward_approval_upgrade import migrate_outward_approval_copy
from orket.adapters.storage.outward_run_event_store import _MIGRATIONS as EVENT_MIGRATIONS
from orket.adapters.storage.outward_run_store import _MIGRATIONS as RUN_MIGRATIONS
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from tests.helpers.outward_authorization import TEST_API_KEY, FixedInputs, approve, outward_api
from tests.helpers.outward_model_admission import count_calls, use_counted_model


async def _legacy_copy(root, monkeypatch, *, status="approval_required", proposal_status="pending"):
    source, backup, destination = [root / name for name in ("source.sqlite3", "backup.sqlite3", "candidate.sqlite3")]
    task = {"description": "retained legacy task", "instruction": "Do not infer execution from this task.",
            "acceptance_contract": {"governed_tool_call": {"tool": "write_file", "args": {"path": "old.txt", "content": "old"}}}}
    async with connect_sqlite_wal(source) as conn:
        await SQLiteMigrationRunner(namespace="outward_runs").apply(conn, RUN_MIGRATIONS[:1])
        await SQLiteMigrationRunner(namespace="outward_approvals").apply(conn, OUTWARD_APPROVAL_MIGRATIONS[:1])
        await conn.execute("""INSERT INTO outward_runs (
            run_id, status, namespace, submitted_at, current_turn, max_turns,
            task_json, policy_overrides_json, pending_proposals_json
        ) VALUES ('legacy-run', ?, 'legacy', '2026-09-10T12:00:00+00:00', 1, 1, ?, ?, ?)""",
            (status, json.dumps(task), '{"approval_required_tools":["write_file"]}', '[{"proposal_id":"legacy-proposal"}]'))
        await conn.execute("""INSERT INTO outward_approval_proposals (
            proposal_id, run_id, namespace, tool, args_preview_json, context_summary,
            risk_level, submitted_at, expires_at, status, operator_ref, decision
        ) VALUES ('legacy-proposal', 'legacy-run', 'legacy', 'write_file', '{}', 'retained history',
            'write', '2026-09-10T12:00:00+00:00', '2026-09-10T12:01:00+00:00', ?, 'operator:legacy', ?)""",
            (proposal_status, "deny" if proposal_status == "denied" else None))
        await conn.commit()
    async with connect_sqlite_wal(source) as conn:
        await SQLiteMigrationRunner(namespace="outward_run_events").apply(conn, EVENT_MIGRATIONS[:1])
        # Retain an old event and commitments; deliberately do not invent a missing submitted event.
        await conn.execute("""INSERT INTO run_events VALUES (
            'legacy-event', 'proposal_made', 'legacy-run', 1, 'legacy-agent',
            '2026-09-10T12:00:01+00:00', '{"retained":"uncertain history"}', 'retained-event-hash', 'retained-chain-hash')""")
        await conn.commit()
    await migrate_outward_approval_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(destination))
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    return destination, task


async def _snapshot(context):
    async with context.outward_approval_service.unit_of_work.transaction():
        pass
    async with connect_sqlite_wal(context.outward_run_store.db_path) as conn:
        result = {}
        for table in ("outward_runs", "outward_approval_proposals_v2", "run_events", "outward_model_attempts_v2", "outward_effects"):
            cursor = await conn.execute(f"SELECT * FROM {table} ORDER BY 1")
            result[table] = await cursor.fetchall()
        return result


@pytest.mark.integration
@pytest.mark.parametrize("status", ["queued", "running", "approval_required", "completed", "failed"])
# Layer: integration
async def test_legacy_run_reentry_preserves_history_without_inventing_admission(tmp_path, monkeypatch, status):
    """Layer: integration. API and direct executor reentry refuse before writing events or calling a model."""
    _destination, task = await _legacy_copy(tmp_path, monkeypatch, status=status)
    use_counted_model(monkeypatch, tmp_path, [{"tool": "write_file", "args": {"path": "old.txt", "content": "old"}}])
    for _restart in range(2):
        async with outward_api(tmp_path, FixedInputs()) as (client, context):
            before = await _snapshot(context)
            response = await client.post("/v1/runs", json={"run_id": "legacy-run", "task": task})
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == "E_OUTWARD_LEGACY_RUN_QUARANTINED"
            with pytest.raises(RuntimeError, match="E_OUTWARD_LEGACY_RUN_QUARANTINED"):
                await context.outward_run_execution_service.start_if_ready("legacy-run")
            assert (await client.get("/v1/runs/legacy-run")).json()["status"] == status
            assert await _snapshot(context) == before
    assert await count_calls(tmp_path) == 0
    assert not await asyncio.to_thread((tmp_path / "old.txt").exists)


@pytest.mark.integration
@pytest.mark.parametrize("endpoint", ["deny", "decision"])
# Layer: integration
async def test_legacy_denial_retry_preserves_uncertain_run_projection(tmp_path, monkeypatch, endpoint):
    """Layer: integration. A retained denial does not finish or rewrite an unbound historical run."""
    await _legacy_copy(tmp_path, monkeypatch, proposal_status="denied")
    async with outward_api(tmp_path, FixedInputs()) as (client, context):
        before = await _snapshot(context)
        payload = {"reason": "retry"} if endpoint == "deny" else {"decision": "deny"}
        response = await client.post(f"/v1/approvals/legacy-proposal/{endpoint}", json=payload)
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "E_OUTWARD_LEGACY_RUN_QUARANTINED"
        assert await _snapshot(context) == before


@pytest.mark.integration
# Layer: integration
async def test_expired_unbound_approval_remains_history_on_reads_and_decisions(tmp_path, monkeypatch):
    """Layer: integration. Queue reads, sweeps and decisions cannot relabel or expire an old unbound proposal."""
    await _legacy_copy(tmp_path, monkeypatch)
    async with outward_api(tmp_path, FixedInputs()) as (client, context):
        before = await _snapshot(context)
        for path in ("/v1/approvals?session_id=legacy-run", "/v1/approvals/legacy-proposal"):
            response = await client.get(path)
            assert response.status_code == 200, response.text
            assert await _snapshot(context) == before
        assert await context.outward_approval_service.expire_due() == []
        for path, payload in (("approve", {}), ("deny", {"reason": "retry"}), ("decision", {"decision": "approve"})):
            response = await client.post(f"/v1/approvals/legacy-proposal/{path}", json=payload)
            assert response.status_code == 409, response.text
            assert response.json()["detail"] == "E_OUTWARD_AUTHORIZATION_REQUIRED"
            assert await _snapshot(context) == before


@pytest.mark.integration
# Layer: integration
async def test_new_admitted_work_can_run_beside_quarantined_legacy_history(tmp_path, monkeypatch):
    """Layer: integration. A fresh separately approved write succeeds without consuming or rewriting the old history."""
    await _legacy_copy(tmp_path, monkeypatch)
    call = {"tool": "write_file", "args": {"path": "new.txt", "content": "new admission"}}
    use_counted_model(monkeypatch, tmp_path, [call])
    async with outward_api(tmp_path, FixedInputs()) as (client, context):
        before = await _snapshot(context)
        response = await client.post("/v1/runs", json={
            "run_id": "new-run", "namespace": "new-scope",
            "task": {"description": "new work", "instruction": "Write only the newly approved file.",
                     "acceptance_contract": {"governed_tool_call": call}},
            "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": 1},
        })
        assert response.status_code == 200, response.text
        proposal = response.json()["pending_proposals"][0]["proposal_id"]
        assert not await asyncio.to_thread((tmp_path / "new.txt").exists)
        assert (await approve(client, proposal)).status_code == 200
        assert await asyncio.to_thread((tmp_path / "new.txt").read_text) == "new admission"
        after = await _snapshot(context)
        for table in ("outward_runs", "outward_approval_proposals_v2", "run_events"):
            assert all(row in after[table] for row in before[table])
        assert (await context.outward_run_store.get("legacy-run")).execution_generation == 0
        assert (await context.outward_run_store.get("new-run")).execution_generation == 1
    assert await count_calls(tmp_path) == 1


@pytest.mark.integration
# Layer: integration
async def test_quarantined_queue_does_not_starve_bound_expiry(tmp_path, monkeypatch):
    """Layer: integration. More than one page of retained old rows cannot hide an admitted deadline from the sweep."""
    destination, _task = await _legacy_copy(tmp_path, monkeypatch)
    inputs = FixedInputs()
    call = {"tool": "write_file", "args": {"path": "new.txt", "content": "must expire"}}
    use_counted_model(monkeypatch, tmp_path, [call])
    async with outward_api(tmp_path, inputs) as (client, context):
        store = context.outward_approval_store
        legacy = await store.get("legacy-proposal")
        async with connect_sqlite_wal(destination) as conn:
            for index in range(500):
                await store.save(replace(legacy, proposal_id=f"legacy-{index:04d}"), connection=conn)
            await conn.commit()
        response = await client.post("/v1/runs", json={
            "run_id": "new-run", "namespace": "new-scope",
            "task": {"description": "new work", "instruction": "Requires a fresh decision.",
                     "acceptance_contract": {"governed_tool_call": call}},
            "policy_overrides": {"approval_required_tools": ["write_file"], "max_turns": 1},
        })
        assert response.status_code == 200, response.text
        proposal_id = response.json()["pending_proposals"][0]["proposal_id"]
        assert proposal_id not in {p.proposal_id for p in await store.list(status="pending", limit=500)}
        inputs.now += timedelta(seconds=600)
        expired = await context.outward_approval_service.expire_due()
        assert [p.proposal_id for p in expired] == [proposal_id]
        assert (await store.get(proposal_id)).status == "expired"
        async with connect_sqlite_wal(destination) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM outward_approval_proposals_v2 WHERE status='pending' AND authorization_json IS NULL")
            assert (await cursor.fetchone())[0] == 501
        assert (await context.outward_run_store.get("legacy-run")).status == "approval_required"
    assert not await asyncio.to_thread((tmp_path / "new.txt").exists)
