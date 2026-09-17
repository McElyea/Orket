"""Layer: integration. Real API/process fencing at the pre-intent recovery boundary."""

from __future__ import annotations

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from tests.helpers.outward_authorization import append_command, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import finish_effect_worker, paused_effect_worker


async def recovery_request(client, proposal_id, *, key="recover-1"):
    inspected = await client.get(f"/v1/approvals/{proposal_id}/effect")
    assert inspected.status_code == 200, inspected.text
    effect = inspected.json()
    return {"request_id": key, "expected_owner_id": effect["owner_id"], "expected_fencing_generation": effect["fencing_generation"]}


async def recover(client, proposal_id, body, **kwargs):
    return await client.post(f"/v1/approvals/{proposal_id}/effect/recover", json=body, **kwargs)


@pytest.mark.integration
# Layer: integration
async def test_recovery_fences_a_live_old_worker_and_preserves_one_effect(tmp_path, boundary, monkeypatch):
    """The replacement executes once; the paused old process fails before it can commit intent."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim") as old:
            body = await recovery_request(client, proposal_id)
            response = await recover(client, proposal_id, body)
            assert response.status_code == 200, response.text
            assert response.json()["effect"]["state"] == "published"
            assert response.json()["effect"]["fencing_generation"] == 2
            old_status, old_body = await finish_effect_worker(old)
            assert old_status == 409 and old_body["detail"] == "E_OUTWARD_EFFECT_FENCE_CONFLICT"
        repeated = await recover(client, proposal_id, body)
        assert repeated.status_code == 200 and repeated.json() == response.json()
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await recover(client, proposal_id, body)).json() == response.json()
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert len(journal) == 5 and effect.fencing_generation == 2
    shared = AsyncControlPlaneRecordRepository(db_path)
    decision = await shared.get_recovery_decision(decision_id=effect.recovery_decision_id)
    action = await shared.get_operator_action(action_id=effect.recovery_decision_id)
    assert decision.authorized_next_action.value == "retry_same_attempt_scope"
    assert action.result == "pre_intent_owner_replaced" and action.actor_ref != "operator:unknown"
    assert action.receipt_refs == [f"owner:{effect.owner_id}:fence:2"]


@pytest.mark.integration
@pytest.mark.parametrize("damage", ["missing-decision", "missing-action", "wrong-action"])
# Layer: integration
async def test_recovery_record_corruption_prevents_claim_dispatch(tmp_path, boundary, monkeypatch, damage):
    """A persisted fence alone cannot authorize execution when its recovery evidence is missing or contradictory."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim"):
            body = await recovery_request(client, proposal_id)
        async with paused_effect_worker(tmp_path, proposal_id, "claim", body) as replacement:
            before = await effect_snapshot(db_path, proposal_id)
            async with connect_sqlite_wal(db_path) as conn:
                if damage == "wrong-action":
                    await conn.execute("""UPDATE recovery_decision_records SET payload_json =
                        json_set(payload_json, '$.authorized_next_action', 'quarantine_run')""")
                else:
                    table = "recovery_decision_records" if damage == "missing-decision" else "operator_action_records"
                    await conn.execute(f"DELETE FROM {table}")
                await conn.commit()
            inspected = await client.get(f"/v1/approvals/{proposal_id}/effect")
            retried = await recover(client, proposal_id, body)
            assert inspected.status_code == retried.status_code == 409
            status, _payload = await finish_effect_worker(replacement)
            assert status == 409
            assert await effect_snapshot(db_path, proposal_id) == before
    assert not (tmp_path / "effects.txt").exists()



@pytest.mark.integration
# Layer: integration
async def test_committed_intent_wins_over_recovery_even_after_owner_death(tmp_path, boundary, monkeypatch):
    """Neither a live nor a terminated owner grants permission to reassign committed intent."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "intent"):
            body = await recovery_request(client, proposal_id)
            before = await effect_snapshot(db_path, proposal_id)
            response = await recover(client, proposal_id, body)
            assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_RECOVERY_REQUIRES_PRE_INTENT_CLAIM"
        response = await recover(client, proposal_id, body)
        assert response.status_code == 409
        assert await effect_snapshot(db_path, proposal_id) == before
    assert not (tmp_path / "effects.txt").exists()


@pytest.mark.integration
@pytest.mark.parametrize("table", ["recovery_decision_records", "operator_action_records"])
# Layer: integration
async def test_recovery_record_failure_rolls_back_owner_and_journal(tmp_path, boundary, monkeypatch, table):
    """A real SQLite failure while publishing recovery cannot leave a new owner or permission."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim") as old:
            body = await recovery_request(client, proposal_id)
            before = await effect_snapshot(db_path, proposal_id)
            async with connect_sqlite_wal(db_path) as conn:
                await conn.execute(f"""CREATE TRIGGER bt1_recovery_abort BEFORE INSERT ON {table}
                    BEGIN SELECT RAISE(ABORT, 'recovery publication failure'); END""")
                await conn.commit()
            response = await recover(client, proposal_id, body)
            assert response.status_code == 500
            assert await effect_snapshot(db_path, proposal_id) == before
            assert not (tmp_path / "effects.txt").exists()
            status, _payload = await finish_effect_worker(old)
            assert status == 200
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]


@pytest.mark.integration
# Layer: integration
async def test_recovery_request_conflicts_and_authentication_cannot_change_owner(tmp_path, boundary, monkeypatch):
    """Unauthenticated, stale-fence and changed-key payloads cannot create execution authority."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim"):
            body = await recovery_request(client, proposal_id)
            before = await effect_snapshot(db_path, proposal_id)
            unauthenticated = await recover(client, proposal_id, body, headers={"X-API-Key": "invalid"})
            assert unauthenticated.status_code in {401, 403}
            stale = await recover(client, proposal_id, {**body, "expected_fencing_generation": 9})
            assert stale.status_code == 409
            assert await effect_snapshot(db_path, proposal_id) == before
            response = await recover(client, proposal_id, body)
            assert response.status_code == 200
            changed = await recover(client, proposal_id, {**body, "expected_owner_id": "different"})
            assert changed.status_code == 409 and changed.json()["detail"] == "E_OUTWARD_RECOVERY_REQUEST_CONFLICT"
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]


@pytest.mark.integration
# Layer: integration
async def test_interrupted_recovery_can_resume_its_claim_but_superseded_request_cannot(tmp_path, boundary, monkeypatch):
    """Repeated recovery keys do not acquire a later fence after another recovery replaces their claim."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim"):
            first = await recovery_request(client, proposal_id)
        async with paused_effect_worker(tmp_path, proposal_id, "claim", first) as replacement:
            second = await recovery_request(client, proposal_id, key="recover-2")
            assert second["expected_fencing_generation"] == 2
            response = await recover(client, proposal_id, second)
            assert response.status_code == 200 and response.json()["effect"]["fencing_generation"] == 3
            status, _payload = await finish_effect_worker(replacement)
            assert status == 409
        superseded = await recover(client, proposal_id, first)
        assert superseded.status_code == 409 and superseded.json()["detail"] == "E_OUTWARD_RECOVERY_SUPERSEDED"
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert effect.fencing_generation == 3 and len(journal) == 6


@pytest.mark.integration
@pytest.mark.parametrize("checkpoint", ["claim", "intent", "dispatch", "receipt", "publication"])
# Layer: integration
async def test_recovery_retries_after_process_death_obey_original_effect_boundary(tmp_path, boundary, monkeypatch, checkpoint):
    """A retained recovery request resumes its own pre-intent claim or receipt, never uncertain execution."""
    db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim"):
            body = await recovery_request(client, proposal_id)
        async with paused_effect_worker(tmp_path, proposal_id, checkpoint, body):
            effect, _journal = await effect_snapshot(db_path, proposal_id)
            assert effect.fencing_generation == 2
    async with outward_api(tmp_path, inputs) as (client, _context):
        response = await recover(client, proposal_id, body)
        again = await recover(client, proposal_id, body)
        allowed = checkpoint in {"claim", "receipt", "publication"}
        assert response.status_code == again.status_code == (200 if allowed else 409), response.text
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert effect.fencing_generation == 2
    assert effect.state == ("published" if allowed else "dispatching")
    target = tmp_path / "effects.txt"
    if checkpoint == "intent":
        assert not target.exists()
    else:
        assert target.read_text().splitlines() == ["effect"]
    if allowed:
        assert len(journal) == 5


@pytest.mark.integration
# Layer: integration
async def test_recovery_key_cannot_be_reused_by_another_authenticated_operator(tmp_path, boundary, monkeypatch):
    """The server-derived operator identity is part of durable recovery request identity."""
    _db_path, inputs, _calls = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls)
        async with paused_effect_worker(tmp_path, proposal_id, "claim"):
            body = await recovery_request(client, proposal_id)
        assert (await recover(client, proposal_id, body)).status_code == 200
    monkeypatch.setenv("ORKET_API_KEY", "second-operator-key")
    async with outward_api(tmp_path, inputs, api_key="second-operator-key") as (client, _context):
        response = await recover(client, proposal_id, body)
        assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_RECOVERY_REQUEST_CONFLICT"
    assert (tmp_path / "effects.txt").read_text().splitlines() == ["effect"]
