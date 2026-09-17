from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.application.services.outward_approval_service import OutwardApprovalService
from tests.helpers.outward_authorization import approve, hold_decision_writers, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary


@pytest.mark.integration
@pytest.mark.parametrize("decision", ["approve", "deny"])
@pytest.mark.parametrize("fault", ["projection", "event", "ledger_head"])
# Layer: integration
async def test_decision_failure_rolls_back_proposal_projection_and_event(tmp_path, boundary, decision, fault):
    """Real SQLite aborts after a decision write cannot leave permission or an effect behind."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1])
        before = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
        target = {
            "projection": "BEFORE UPDATE ON outward_runs", "event": "BEFORE INSERT ON run_events",
            "ledger_head": "BEFORE UPDATE ON outward_ledger_heads_v2",
        }[fault]
        async with connect_sqlite_wal(db_path) as conn:
            await conn.execute(f"CREATE TRIGGER bt1_abort {target} BEGIN SELECT RAISE(ABORT, 'bt1 injected failure'); END")
            await conn.commit()
        response = await client.post(
            f"/v1/approvals/{proposal_id}/{decision}", json={"reason": "test denial"} if decision == "deny" else {},
        )
        assert response.status_code == 500, response.text
    assert (await OutwardApprovalStore(db_path).get(proposal_id)).status == "pending"
    run = await OutwardRunStore(db_path).get("bt0-run")
    assert run.status == "approval_required" and run.pending_proposals[0]["proposal_id"] == proposal_id
    assert await OutwardRunEventStore(db_path).list_for_run("bt0-run") == before
    assert not (tmp_path / "first.txt").exists()
    async with connect_sqlite_wal(db_path) as conn:
        await conn.execute("DROP TRIGGER bt1_abort")
        await conn.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        repaired = await client.post(
            f"/v1/approvals/{proposal_id}/{decision}", json={"reason": "test denial"} if decision == "deny" else {},
        )
        assert repaired.status_code == 200, repaired.text
    assert (await OutwardApprovalStore(db_path).get(proposal_id)).status == {"approve": "approved", "deny": "denied"}[decision]
    assert (tmp_path / "first.txt").exists() is (decision == "approve")


@pytest.mark.integration
# Layer: integration
async def test_deadline_is_sampled_after_waiting_for_the_database_writer(tmp_path, boundary, monkeypatch):
    """Crossing the deadline while SQLite is locked cannot retain an earlier approval timestamp."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1], approval_seconds=10)
        task = None
        try:
            async with hold_decision_writers(db_path, monkeypatch, writers=1) as waiting:
                task = asyncio.create_task(approve(client, proposal_id))
                await asyncio.wait_for(waiting.wait(), timeout=4)
                inputs.now += timedelta(seconds=11)
            response = await asyncio.wait_for(task, timeout=10)
            assert response.status_code == 200, response.text
            assert response.json()["approval"]["status"] == "expired"
        finally:
            if task is not None:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    proposal = await OutwardApprovalStore(db_path).get(proposal_id)
    assert proposal.decided_at == inputs.utc_now_iso()
    assert proposal.operator_ref == "system:timeout"
    assert not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_direct_expiry_is_independent_of_the_500_row_scan_cap(tmp_path, boundary):
    """A pending proposal outside the queue's first page cannot be approved after its deadline."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1], approval_seconds=10)
        store = context.outward_approval_store
        proposal = await store.get(proposal_id)
        async with connect_sqlite_wal(db_path) as conn:
            for index in range(501):
                await store.save(replace(
                    proposal, proposal_id=f"decoy:{index:04d}", expires_at=inputs.utc_now_iso(),
                    authorization_json=None, authorization_digest=None,
                ), connection=conn)
            await conn.commit()
        first_page = await store.list(status="pending", limit=500)
        assert len(first_page) == 500 and proposal_id not in {row.proposal_id for row in first_page}
        inputs.now += timedelta(seconds=11)
        response = await approve(client, proposal_id)
        assert response.status_code == 200, response.text
        assert response.json()["approval"]["status"] == "expired"
    assert not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_pending_proposal_publication_rolls_back_on_event_failure(tmp_path, boundary):
    """Failure to publish the pending event cannot leave a proposal or pending run projection."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        submitted = await client.post("/v1/runs", json={
            "run_id": "bt0-run", "task": {"description": "pending rollback", "instruction": "wait"},
            "policy_overrides": {"approval_required_tools": ["write_file"]},
        })
        assert submitted.status_code == 200 and submitted.json()["status"] == "queued"
        before = await context.outward_run_event_store.list_for_run("bt0-run")
        async with connect_sqlite_wal(db_path) as conn:
            await conn.execute("""CREATE TRIGGER bt1_pending_abort BEFORE INSERT ON run_events
                WHEN NEW.event_type = 'proposal_pending_approval'
                BEGIN SELECT RAISE(ABORT, 'bt1 injected failure'); END""")
            await conn.commit()
        with pytest.raises(aiosqlite.IntegrityError, match="bt1 injected failure"):
            await context.outward_approval_service.request_tool_approval(
                run_id="bt0-run", tool="write_file", args=calls[0]["args"], context_summary="atomic pending",
            )
    assert await OutwardApprovalStore(db_path).list(run_id="bt0-run", status=None) == []
    run = await OutwardRunStore(db_path).get("bt0-run")
    assert run.status == "queued" and run.pending_proposals == ()
    assert await OutwardRunEventStore(db_path).list_for_run("bt0-run") == before


@pytest.mark.integration
# Layer: integration
async def test_mismatched_database_paths_refuse_decision_before_mutation(tmp_path, boundary):
    """Cross-database configuration cannot fall back to separately committed approval writes."""
    db_path, inputs, calls = boundary
    other_path = tmp_path / "other-events.sqlite3"
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1])
        service = OutwardApprovalService(
            approval_store=context.outward_approval_store, run_store=context.outward_run_store,
            event_store=OutwardRunEventStore(other_path), workspace_root=tmp_path,
            connector_registry=context.outward_approval_service.connector_registry, utc_now=inputs.utc_now_iso,
        )
        with pytest.raises(RuntimeError, match="E_OUTWARD_TRANSACTION_DATABASE_MISMATCH"):
            await service.approve(proposal_id, operator_ref="operator:fixture")
    assert (await OutwardApprovalStore(db_path).get(proposal_id)).status == "pending"
    assert not other_path.exists()
    assert not (tmp_path / "first.txt").exists()


@pytest.mark.integration
@pytest.mark.parametrize("competitor", ["approve", "deny", "expire"])
# Layer: integration
async def test_independent_authenticated_processes_publish_one_operator_decision(tmp_path, boundary, competitor):
    """Layer: integration. Initialized workers contend at the real decision lock and retain one decision."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1], approval_seconds=10)
    workers = []
    try:
        for index, decision in enumerate(("approve", competitor)):
            workers.append(await asyncio.create_subprocess_exec(
                sys.executable, "-m", "tests.helpers.outward_decision_worker",
                str(tmp_path), proposal_id, decision, f"bt1-test-{decision}-{index}-key",
                cwd=await asyncio.to_thread(lambda: Path(__file__).resolve().parents[2]),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            ))
        await asyncio.wait_for(asyncio.gather(*[
            _await_worker_signal(worker, b"BT1_SCHEMA_READY") for worker in workers
        ]), timeout=15)
        async with connect_sqlite_wal(db_path) as lock:
            await lock.execute("BEGIN IMMEDIATE")
            try:
                for worker in workers:
                    worker.stdin.write(b"decide\n")
                    await worker.stdin.drain()
                await asyncio.wait_for(asyncio.gather(*[
                    _await_worker_signal(worker, b"BT1_WRITER_WAITING") for worker in workers
                ]), timeout=10)
            finally:
                await lock.rollback()
        output = await asyncio.wait_for(asyncio.gather(*[worker.communicate() for worker in workers]), timeout=15)
        responses = []
        for worker, (stdout, stderr) in zip(workers, output, strict=True):
            assert worker.returncode == 0, stderr.decode(errors="replace")
            line = next(line for line in stdout.decode().splitlines() if line.startswith("BT1_RESPONSE="))
            responses.append(json.loads(line.removeprefix("BT1_RESPONSE=")))
    finally:
        for worker in workers:
            if worker.returncode is None:
                worker.kill()
            await worker.wait()
    proposal = await OutwardApprovalStore(db_path).get(proposal_id)
    assert any(status == 200 for status, _body in responses), responses
    for status, body in responses:
        if status == 409:
            assert competitor == "approve" and body["detail"] == "E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN"
        else:
            assert status == 200 and body["approval"] == proposal.to_decision_payload(), responses
    assert proposal.operator_ref != "operator:unknown"
    events = await OutwardRunEventStore(db_path).list_for_run("bt0-run")
    decisions = [event for event in events if event.event_type in {"proposal_approved", "proposal_denied", "proposal_expired"}]
    assert len(decisions) == 1 and decisions[0].payload == proposal.to_decision_payload()
    assert (tmp_path / "first.txt").exists() is (proposal.status == "approved")
    if proposal.status == "expired":
        assert proposal.operator_ref == "system:timeout"
    assert sum(event.event_type == "tool_invoked" for event in events) == int(proposal.status == "approved")
    run = await OutwardRunStore(db_path).get("bt0-run")
    assert run.status == ("failed" if proposal.status == "expired" else "completed")


async def _await_worker_signal(worker, signal):
    while line := await worker.stdout.readline():
        if line.strip() == signal:
            return
    raise AssertionError(f"Independent worker exited before {signal.decode()}")
