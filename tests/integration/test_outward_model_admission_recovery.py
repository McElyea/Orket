"""Layer: integration. Real API, SQLite, evidence files and worker-death model admission proof."""

from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from tests.helpers.outward_authorization import approve, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import finish_effect_worker, paused_effect_worker
from tests.helpers.outward_model_admission import (
    admission_snapshot,
    count_calls,
    queue_run,
    retry_run,
    use_counted_model,
)


@pytest.mark.integration
# Layer: integration
async def test_run_reentry_recovers_next_model_admission_after_effect_publication(tmp_path, boundary):
    """A restarted public run submission must admit the pending turn without replaying an earlier effect."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
    async with paused_effect_worker(tmp_path, proposal_id, "publication"):
        effect, _journal = await effect_snapshot(db_path, proposal_id)
        assert effect.state == "published"
    before = await OutwardRunStore(db_path).get("bt0-run")
    assert before.status == "running" and before.current_turn == 2 and before.pending_proposals == ()
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
    assert not (tmp_path / "second.txt").exists()
    async with outward_api(tmp_path, inputs) as (client, _context):
        retried_approval = await approve(client, proposal_id)
        assert retried_approval.status_code == 200
        assert await OutwardRunStore(db_path).get("bt0-run") == before
        second_proposal = await submit_sequence(client, calls)
        assert second_proposal != proposal_id
        assert not (tmp_path / "second.txt").exists()
        assert (await approve(client, second_proposal)).status_code == 200
    assert await asyncio.to_thread((tmp_path / "second.txt").read_text) == calls[1]["args"]["content"]


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["model_ready", "model_claim", "model_response", "model_result", "model_publication"])
# Layer: integration
async def test_model_admission_crash_boundaries(tmp_path, boundary, monkeypatch, checkpoint):
    """Only ready or retained-result work resumes; an ambiguous invocation never triggers a second producer."""
    db_path, inputs, calls = boundary
    calls = calls[:1]
    use_counted_model(monkeypatch, tmp_path, calls)
    queued = await queue_run(tmp_path, inputs, calls)
    async with paused_effect_worker(tmp_path, "bt0-run", checkpoint):
        before = await admission_snapshot(db_path)
    async with outward_api(tmp_path, inputs) as (client, _context):
        response = await retry_run(client, queued)
        if checkpoint in {"model_claim", "model_response"}:
            assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_MODEL_ADMISSION_UNRESOLVED"
            assert await admission_snapshot(db_path) == before
            assert await count_calls(tmp_path) == (1 if checkpoint == "model_response" else 0)
            assert not (tmp_path / "first.txt").exists()
            return
        assert response.status_code == 200 and response.json()["status"] == "approval_required", response.text
        published = await admission_snapshot(db_path)
        assert published.state == "published" and await count_calls(tmp_path) == 1
        if before.state in {"observed", "published"}:
            assert published.result_digest == before.result_digest
        proposals = await OutwardApprovalStore(db_path).list(run_id=queued.run_id)
        assert len(proposals) == 1
        proposal_id = proposals[0].proposal_id
        assert not (tmp_path / "first.txt").exists()
        assert (await approve(client, proposal_id)).status_code == 200
        assert (await retry_run(client, queued)).json()["status"] == "completed"
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
    assert await count_calls(tmp_path) == 1


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["model_response", "model_result"])
# Layer: integration
async def test_competing_model_producer_is_refused_and_retained_publication_is_idempotent(tmp_path, boundary, monkeypatch, checkpoint):
    """Separate live workers share one owner; a late owner response cannot overwrite the committed proposal."""
    db_path, inputs, calls = boundary
    calls = calls[:1]
    use_counted_model(monkeypatch, tmp_path, calls)
    queued = await queue_run(tmp_path, inputs, calls)
    async with paused_effect_worker(tmp_path, "bt0-run", checkpoint) as worker:
        async with outward_api(tmp_path, inputs) as (client, _context):
            retry = await retry_run(client, queued)
            assert retry.status_code == (409 if checkpoint == "model_response" else 200)
            assert await count_calls(tmp_path) == 1
        status, payload = await finish_effect_worker(worker)
        assert status == 200 and payload["status"] == "approval_required"
        if checkpoint == "model_result":
            assert payload == retry.json()
    before = await admission_snapshot(db_path)
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await retry_run(client, queued)).json() == payload
    assert before == await admission_snapshot(db_path)
    assert await count_calls(tmp_path) == 1 and not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_model_publication_transaction_abort_retains_result_for_restart(tmp_path, boundary, monkeypatch):
    """Failure inserting approval rolls back model event/projection/publication, while its observation stays retained."""
    db_path, inputs, calls = boundary
    calls = calls[:1]
    use_counted_model(monkeypatch, tmp_path, calls)
    queued = await queue_run(tmp_path, inputs, calls)
    async with paused_effect_worker(tmp_path, "bt0-run", "model_result"):
        before = await admission_snapshot(db_path)
    events_before = await OutwardRunEventStore(db_path).list_for_run(queued.run_id)
    async with connect_sqlite_wal(db_path) as connection:
        await connection.execute("""CREATE TRIGGER reject_model_approval BEFORE INSERT ON outward_approval_proposals_v2
            BEGIN SELECT RAISE(ABORT, 'test publication failure'); END""")
        await connection.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await retry_run(client, queued)).status_code == 500
    assert await admission_snapshot(db_path) == before
    assert (await OutwardRunStore(db_path).get(queued.run_id)).status == "running"
    assert await OutwardApprovalStore(db_path).list(run_id=queued.run_id) == []
    events = await OutwardRunEventStore(db_path).list_for_run(queued.run_id)
    assert events == events_before
    assert sorted(event.event_type for event in events) == ["run_started", "run_submitted", "turn_started"]
    async with connect_sqlite_wal(db_path) as connection:
        await connection.execute("DROP TRIGGER reject_model_approval")
        await connection.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        response = await retry_run(client, queued)
        assert response.status_code == 200 and response.json()["status"] == "approval_required"
        proposal = response.json()["pending_proposals"][0]["proposal_id"]
        assert (await approve(client, proposal)).status_code == 200
    assert await count_calls(tmp_path) == 1
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]


@pytest.mark.integration
@pytest.mark.parametrize("damage", ["artifact", "input"])
# Layer: integration
async def test_model_admission_rejects_evidence_and_input_drift_without_repair(tmp_path, boundary, monkeypatch, damage):
    """Retained evidence cannot be resealed, and changed run inputs cannot acquire the observed call."""
    db_path, inputs, calls = boundary
    use_counted_model(monkeypatch, tmp_path, calls)
    queued = await queue_run(tmp_path, inputs, calls[:1])
    async with paused_effect_worker(tmp_path, "bt0-run", "model_result"):
        before = await admission_snapshot(db_path)
    evidence_path = tmp_path / before.result["model_invocation"]["proposal_extraction_ref"]
    if damage == "artifact":
        await asyncio.to_thread(evidence_path.write_text, '{"tampered":true}\n')
    else:
        async with connect_sqlite_wal(db_path) as connection:
            await connection.execute("UPDATE outward_runs SET task_json = json_set(task_json, '$.instruction', 'changed')")
            await connection.commit()
    evidence_before = await asyncio.to_thread(evidence_path.read_bytes)
    async with outward_api(tmp_path, inputs) as (client, _context):
        response = await retry_run(client, queued)
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == (
            "E_OUTWARD_MODEL_EVIDENCE_DIGEST" if damage == "artifact" else "E_OUTWARD_AUTHORITY_INPUT_DRIFT"
        )
    assert before == await admission_snapshot(db_path)
    assert await asyncio.to_thread(evidence_path.read_bytes) == evidence_before
    assert await count_calls(tmp_path) == 1 and not (tmp_path / "first.txt").exists()
    assert await OutwardApprovalStore(db_path).list(run_id=queued.run_id) == []


@pytest.mark.integration
# Layer: integration
async def test_initial_admission_failure_rolls_back_run_start_and_events(tmp_path, boundary, monkeypatch):
    """A real SQLite rejection prevents both model invocation and a misleading running projection."""
    db_path, inputs, calls = boundary
    use_counted_model(monkeypatch, tmp_path, calls)
    queued = await queue_run(tmp_path, inputs, calls[:1])
    assert await admission_snapshot(db_path) is None
    events_before = await OutwardRunEventStore(db_path).list_for_run(queued.run_id)
    async with connect_sqlite_wal(db_path) as connection:
        await connection.execute("""CREATE TRIGGER reject_initial_admission BEFORE INSERT ON outward_model_attempts_v2
            BEGIN SELECT RAISE(ABORT, 'test admission failure'); END""")
        await connection.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await retry_run(client, queued)).status_code == 500
    assert await OutwardRunStore(db_path).get(queued.run_id) == queued
    assert await OutwardRunEventStore(db_path).list_for_run(queued.run_id) == events_before
    assert await admission_snapshot(db_path) is None and await count_calls(tmp_path) == 0
    async with connect_sqlite_wal(db_path) as connection:
        await connection.execute("DROP TRIGGER reject_initial_admission")
        await connection.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await retry_run(client, queued)).json()["status"] == "approval_required"
    assert await count_calls(tmp_path) == 1 and not (tmp_path / "first.txt").exists()


@pytest.mark.integration
@pytest.mark.parametrize("statement", [
    "UPDATE outward_model_attempts_v2 SET owner_id = 'replacement'",
    "UPDATE outward_model_attempts_v2 SET result_json = '{}'",
    "UPDATE outward_model_attempts_v2 SET inputs_json = '{}'",
    "DELETE FROM outward_model_attempts_v2",
    "INSERT OR REPLACE INTO outward_model_attempts_v2 SELECT * FROM outward_model_attempts_v2",
])
# Layer: integration
async def test_model_admission_sql_guards_retain_original_ownership_and_evidence(tmp_path, boundary, statement):
    """Persisted ownership and result protections reject direct mutation through another real connection."""
    import sqlite3

    db_path, inputs, calls = boundary
    await queue_run(tmp_path, inputs, calls[:1])
    async with paused_effect_worker(tmp_path, "bt0-run", "model_result"):
        before = await admission_snapshot(db_path)
    async with connect_sqlite_wal(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="E_OUTWARD_MODEL_ADMISSION"):
            await connection.execute(statement)
        await connection.rollback()
    assert await admission_snapshot(db_path) == before
    assert await count_calls(tmp_path) == 1 and not (tmp_path / "first.txt").exists()
