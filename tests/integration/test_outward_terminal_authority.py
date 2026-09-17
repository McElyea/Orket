"""Terminal projection contradictions and failure at the final ledger append."""

from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.core.domain import AttemptState, RunState
from tests.helpers.outward_authorization import (
    append_command,
    approve,
    effect_snapshot,
    outward_api,
    submit_sequence,
)
from tests.helpers.outward_authorization import boundary as boundary

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("corruption", ["run_state", "attempt_state", "end_timestamp", "step_result", "step_inputs"])
# Layer: integration
async def test_terminal_projection_refuses_contradictory_shared_records(tmp_path, boundary, corruption):
    _, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1])
        response = await approve(client, proposal_id)
        assert response.status_code == 200, response.text
        summary = await context.outward_run_inspection_service.summary("bt0-run")
        assert summary["terminal"] and summary["final_truth"]["result_class"] == "success"
        async with context.outward_approval_service.unit_of_work.transaction() as transaction:
            cp = transaction.control_plane
            run = await cp.execution.get_run_record(run_id="bt0-run")
            attempt = await cp.execution.get_attempt_record(attempt_id=run.current_attempt_id)
            truth = await cp.records.get_final_truth(run_id=run.run_id)
            step = await cp.execution.get_step_record(step_id=truth.authoritative_result_ref)
            if corruption == "run_state":
                await cp.execution.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
            elif corruption in {"attempt_state", "end_timestamp"}:
                update = {"attempt_state": AttemptState.FAILED} if corruption == "attempt_state" else {"end_timestamp": "2026-09-11T12:00:01+00:00"}
                await cp.execution.save_attempt_record(record=attempt.model_copy(update=update))
            else:
                update = {"observed_result_classification": "failed"} if corruption == "step_result" else {"input_ref": "other-inputs"}
                damaged = step.model_copy(update=update)
                if corruption == "step_inputs":
                    # Corrupt retained authority directly; legitimate writes cannot rebind it.
                    await transaction._connection.execute(
                        "UPDATE control_plane_steps SET payload_json=? WHERE step_id=?",
                        (damaged.model_dump_json(), step.step_id),
                    )
                else:
                    await cp.execution.save_step_record(record=damaged)
        with pytest.raises(RuntimeError, match="E_OUTWARD_FINAL_TRUTH_PROJECTION_CONFLICT"):
            await context.outward_run_inspection_service.summary("bt0-run")
        status = await client.get("/v1/runs/bt0-run")
        assert status.status_code == 500, status.text


@pytest.mark.parametrize("outcome", ["success", "denied"])
# Layer: integration
async def test_terminal_append_failure_rolls_back_authority_and_retry_preserves_effect(tmp_path, boundary, monkeypatch, outcome):
    db, inputs, _ = boundary
    calls = append_command(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls)
        append = OutwardStoreTransaction.append_event

        async def fail_terminal(transaction, event):
            if event.event_type == "run_completed":
                raise RuntimeError("injected terminal append failure")
            return await append(transaction, event)

        async def decide():
            return await approve(client, proposal_id) if outcome == "success" else await client.post(
                f"/v1/approvals/{proposal_id}/deny", json={"reason": "declined"},
            )

        with monkeypatch.context() as patch:
            patch.setattr(OutwardStoreTransaction, "append_event", fail_terminal)
            response = await decide()
            assert response.status_code == 409, response.text
        async with context.outward_approval_service.unit_of_work.transaction() as transaction:
            assert await transaction.control_plane.records.get_final_truth(run_id="bt0-run") is None
            run = await transaction.control_plane.execution.get_run_record(run_id="bt0-run")
            assert run.lifecycle_state is RunState.EXECUTING and run.final_truth_record_id is None
            approval = await transaction.get_proposal(proposal_id)
            assert approval.status == ("approved" if outcome == "success" else "pending")
        if outcome == "success":
            effect, _ = await effect_snapshot(db, proposal_id)
            assert effect.state == "observed"
        retried = await decide()
        assert retried.status_code == 200, retried.text
        status = (await client.get("/v1/runs/bt0-run")).json()
        assert status["final_truth"]["result_class"] == ("success" if outcome == "success" else "blocked")
        assert (tmp_path / "effects.txt").exists() == (outcome == "success")
        if outcome == "success":
            assert await asyncio.to_thread((tmp_path / "effects.txt").read_text) == "effect\n"
        terminal = [event for event in await context.outward_run_event_store.list_for_run("bt0-run")
                    if event.event_type in {"run_completed", "run_failed"}]
        assert len(terminal) == 1
