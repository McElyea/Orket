"""Layer: integration. Explicit recovery with live competing workers and retained attempt evidence."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from tests.helpers.outward_authorization import approve, outward_api
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import finish_effect_worker, paused_effect_worker
from tests.helpers.outward_model_admission import (
    admission_snapshot,
    count_calls,
    queue_run,
    retry_run,
    use_counted_model,
)


async def recovery_request(client, *, key="model-recovery-1"):
    response = await client.get("/v1/runs/bt0-run/model-admission")
    assert response.status_code == 200, response.text
    current = response.json()["admission"]
    return {"request_id": key, "execution_generation": current["execution_generation"], "turn": current["turn"],
            "step_index": current["step_index"], "expected_owner_id": current["owner_id"],
            "expected_fencing_generation": current["fencing_generation"]}


async def recover(client, body):
    return await client.post("/v1/runs/bt0-run/model-admission/recover", json=body)


@pytest.mark.integration
# Layer: integration
async def test_model_replacement_fences_live_old_response_without_overwriting_evidence(tmp_path, boundary, monkeypatch):
    """The old provider finishes after replacement publication; only the new call can authorize the actual file."""
    db_path, inputs, calls = boundary
    queued = await queue_run(tmp_path, inputs, calls[:1])
    replacement_calls = [{"tool": "write_file", "args": {"path": "first.txt", "content": "replacement authorized content"}}]
    use_counted_model(monkeypatch, tmp_path, replacement_calls)
    async with paused_effect_worker(tmp_path, "bt0-run", "model_provider") as old_worker:
        old = await admission_snapshot(db_path)
        assert old.state == "claimed" and await count_calls(tmp_path) == 1
        async with outward_api(tmp_path, inputs) as (client, _context):
            body = await recovery_request(client)
            recovered = await recover(client, body)
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["admission"]["state"] == "ready" and await count_calls(tmp_path) == 1
            response = await retry_run(client, queued)
            assert response.status_code == 200 and response.json()["status"] == "approval_required", response.text
            winner = await admission_snapshot(db_path)
            assert winner.fencing_generation == 2 and winner.state == "published"
            evidence_path = tmp_path / winner.result["model_invocation"]["model_invocation_ref"]
            evidence_before = await asyncio.to_thread(evidence_path.read_bytes)
            old_status, old_payload = await finish_effect_worker(old_worker)
            assert old_status == 409 and old_payload["detail"] == "E_OUTWARD_MODEL_ADMISSION_FENCE_CONFLICT"
            assert await asyncio.to_thread(evidence_path.read_bytes) == evidence_before
            inspection = await client.get("/v1/runs/bt0-run/model-admission")
            attempts = inspection.json()["attempts"]
            assert [a["state"] for a in attempts] == ["claimed", "published"]
            assert "replacement authorized content" not in inspection.text and "inputs_json" not in inspection.text
            assert attempts[0]["owner_id"] == old.owner_id and attempts[1]["owner_id"] != old.owner_id
            proposal_id = response.json()["pending_proposals"][0]["proposal_id"]
            assert not (tmp_path / "first.txt").exists()
            assert (await approve(client, proposal_id)).status_code == 200
            assert (await recover(client, body)).json()["admission"]["attempt_id"] == winner.attempt_id
    assert await count_calls(tmp_path) == 2
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == replacement_calls[0]["args"]["content"]
    original_artifacts = list((tmp_path / "workspace").rglob(f"{old.evidence_scope}/model_invocation_turn_1.json"))
    assert len(original_artifacts) == 1 and original_artifacts[0] != evidence_path
    events = await OutwardRunEventStore(db_path).list_for_run(queued.run_id)
    proposals = [event for event in events if event.event_type == "proposal_made"]
    assert len(proposals) == 1 and proposals[0].payload["model_invocation_sha256"] == hashlib.sha256(evidence_before).hexdigest()
    shared = AsyncControlPlaneRecordRepository(db_path)
    decision = await shared.get_recovery_decision(decision_id=winner.recovery_decision_id)
    assert decision.failed_attempt_id == old.attempt_id and decision.new_attempt_id == winner.attempt_id
    assert "provider_execution_and_cost:unknown" in decision.required_precondition_refs


@pytest.mark.integration
# Layer: integration
async def test_model_recovery_retries_share_one_new_attempt_after_response_loss(tmp_path, boundary, monkeypatch):
    """A killed recovery response and concurrent retries retain one ready attempt and no extra provider call."""
    db_path, inputs, calls = boundary
    queued = await queue_run(tmp_path, inputs, calls[:1])
    use_counted_model(monkeypatch, tmp_path, calls)
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_provider"):
            body = await recovery_request(client)
        async with paused_effect_worker(tmp_path, "bt0-run", "model_recovery", body):
            before = await admission_snapshot(db_path)
        first, second = await asyncio.gather(recover(client, body), recover(client, body))
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json() and before == await admission_snapshot(db_path)
        assert before.state == "ready" and before.fencing_generation == 2 and await count_calls(tmp_path) == 1
        assert (await retry_run(client, queued)).json()["status"] == "approval_required"
        assert (await recover(client, body)).json()["admission"]["state"] == "published"
    assert await count_calls(tmp_path) == 2 and not (tmp_path / "first.txt").exists()


@pytest.mark.integration
@pytest.mark.parametrize("table", ["recovery_decision_records", "operator_action_records", "outward_model_attempts_v2"])
# Layer: integration
async def test_model_recovery_record_failure_rolls_back_replacement(tmp_path, boundary, table):
    """Actual insert failure preserves the old claim and leaves no partial recovery authority."""
    db_path, inputs, calls = boundary
    await queue_run(tmp_path, inputs, calls[:1])
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_claim"):
            body = await recovery_request(client)
        old = await admission_snapshot(db_path)
        async with connect_sqlite_wal(db_path) as connection:
            await connection.execute(f"CREATE TRIGGER reject_recovery_insert BEFORE INSERT ON {table} "
                                     "BEGIN SELECT RAISE(ABORT, 'test model recovery failure'); END")
            await connection.commit()
        assert (await recover(client, body)).status_code == 500
        assert old == await admission_snapshot(db_path)
        async with connect_sqlite_wal(db_path) as connection:
            for name in ("recovery_decision_records", "operator_action_records"):
                assert (await (await connection.execute(f"SELECT COUNT(*) FROM {name}")).fetchone())[0] == 0
            await connection.execute("DROP TRIGGER reject_recovery_insert")
            await connection.commit()
        assert (await recover(client, body)).status_code == 200
    assert await count_calls(tmp_path) == 0 and not (tmp_path / "first.txt").exists()


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["model_result", "model_publication"])
# Layer: integration
async def test_observed_model_result_prevents_replacement(tmp_path, boundary, checkpoint):
    """Once observation wins, explicit recovery cannot discard it in favor of another provider output."""
    db_path, inputs, calls = boundary
    await queue_run(tmp_path, inputs, calls[:1])
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", checkpoint):
            body = await recovery_request(client)
        before = await admission_snapshot(db_path)
        response = await recover(client, body)
        assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_MODEL_RECOVERY_REQUIRES_UNOBSERVED_CLAIM"
        assert before == await admission_snapshot(db_path)
    assert await count_calls(tmp_path) == 1


@pytest.mark.integration
@pytest.mark.parametrize("damage", ["missing_decision", "missing_action", "changed_actor", "missing_predecessor"])
# Layer: integration
async def test_model_recovery_evidence_damage_blocks_continuation_without_repair(tmp_path, boundary, monkeypatch, damage):
    """A fence alone cannot authorize the replacement when its retained recovery commitment fails."""
    db_path, inputs, calls = boundary
    queued = await queue_run(tmp_path, inputs, calls[:1])
    use_counted_model(monkeypatch, tmp_path, calls)
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_claim"):
            body = await recovery_request(client)
        assert (await recover(client, body)).status_code == 200
        before = await admission_snapshot(db_path)
        async with connect_sqlite_wal(db_path) as connection:
            if damage == "changed_actor":
                await connection.execute("UPDATE operator_action_records SET payload_json = json_set(payload_json, '$.actor_ref', 'changed')")
            elif damage == "missing_predecessor":
                await connection.execute("DROP TRIGGER outward_model_attempt_delete")
                await connection.execute("DELETE FROM outward_model_attempts_v2 WHERE fencing_generation = 1")
            else:
                table = "recovery_decision_records" if damage == "missing_decision" else "operator_action_records"
                await connection.execute(f"DELETE FROM {table}")
            await connection.commit()
        assert (await client.get("/v1/runs/bt0-run/model-admission")).status_code == 409
        assert (await recover(client, body)).status_code == 409
        assert (await retry_run(client, queued)).status_code == 409
        assert before == await admission_snapshot(db_path)
    assert await count_calls(tmp_path) == 0 and not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_model_recovery_authentication_and_request_identity_are_enforced(tmp_path, boundary, monkeypatch):
    """Unauthenticated/stale/forged-body requests and another operator cannot acquire replacement authority."""
    db_path, inputs, calls = boundary
    await queue_run(tmp_path, inputs, calls[:1])
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_claim"):
            body = await recovery_request(client)
        endpoint = "/v1/runs/bt0-run/model-admission/recover"
        assert (await client.post(endpoint, json=body, headers={"X-API-Key": "wrong"})).status_code == 403
        assert (await recover(client, {**body, "operator_ref": "forged"})).status_code == 422
        assert (await recover(client, {**body, "expected_owner_id": "stale"})).status_code == 409
        assert (await recover(client, {**body, "expected_fencing_generation": True})).status_code == 422
        assert (await recover(client, body)).status_code == 200
        assert (await recover(client, {**body, "expected_fencing_generation": 9})).status_code == 409
        before = await admission_snapshot(db_path)
    monkeypatch.setenv("ORKET_API_KEY", "another-model-operator")
    async with outward_api(tmp_path, inputs, api_key="another-model-operator") as (client, _context):
        response = await recover(client, body)
        assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_MODEL_RECOVERY_REQUEST_CONFLICT"
    assert before == await admission_snapshot(db_path) and await count_calls(tmp_path) == 0
    assert await OutwardApprovalStore(db_path).list(run_id="bt0-run") == []


@pytest.mark.integration
# Layer: integration
async def test_old_model_recovery_request_cannot_advance_a_later_turn(tmp_path, boundary, monkeypatch):
    """A recovery retry returns its original published attempt while the next turn awaits its own approval."""
    db_path, inputs, calls = boundary
    queued = await queue_run(tmp_path, inputs, calls)
    use_counted_model(monkeypatch, tmp_path, calls)
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_claim"):
            body = await recovery_request(client)
        assert (await recover(client, body)).status_code == 200
        response = await retry_run(client, queued)
        first_proposal = response.json()["pending_proposals"][0]["proposal_id"]
        assert (await approve(client, first_proposal)).status_code == 200
        before = await OutwardRunStore(db_path).get(queued.run_id)
        assert before.current_turn == 2 and before.status == "approval_required"
        assert (await recover(client, body)).json()["admission"]["turn"] == 1
        assert before == await OutwardRunStore(db_path).get(queued.run_id)
    assert await count_calls(tmp_path) == 2 and not (tmp_path / "second.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_successive_model_replacements_retain_history_and_refuse_superseded_requests(tmp_path, boundary, monkeypatch):
    """A lost replacement response needs a new explicit recovery; old request keys cannot increment its fence again."""
    db_path, inputs, calls = boundary
    queued = await queue_run(tmp_path, inputs, calls[:1])
    use_counted_model(monkeypatch, tmp_path, calls)
    async with outward_api(tmp_path, inputs) as (client, _context):
        async with paused_effect_worker(tmp_path, "bt0-run", "model_claim"):
            first_body = await recovery_request(client)
        assert (await recover(client, first_body)).status_code == 200
        async with paused_effect_worker(tmp_path, "bt0-run", "model_provider") as old_replacement:
            assert (await retry_run(client, queued)).status_code == 409
            before = await admission_snapshot(db_path)
            repeated = await recover(client, first_body)
            assert repeated.status_code == 200 and repeated.json()["admission"]["state"] == "claimed"
            assert before == await admission_snapshot(db_path) and await count_calls(tmp_path) == 1
            second_body = await recovery_request(client, key="model-recovery-2")
            assert (await recover(client, second_body)).status_code == 200
            superseded = await recover(client, first_body)
            assert superseded.status_code == 409 and superseded.json()["detail"] == "E_OUTWARD_MODEL_RECOVERY_SUPERSEDED"
            response = await retry_run(client, queued)
            assert response.status_code == 200 and response.json()["status"] == "approval_required"
            status, payload = await finish_effect_worker(old_replacement)
            assert status == 409 and payload["detail"] == "E_OUTWARD_MODEL_ADMISSION_FENCE_CONFLICT"
        inspection = (await client.get("/v1/runs/bt0-run/model-admission")).json()
        assert [attempt["fencing_generation"] for attempt in inspection["attempts"]] == [1, 2, 3]
        assert [attempt["state"] for attempt in inspection["attempts"]] == ["claimed", "claimed", "published"]
        proposal_id = response.json()["pending_proposals"][0]["proposal_id"]
        assert (await approve(client, proposal_id)).status_code == 200
    assert await count_calls(tmp_path) == 2
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
