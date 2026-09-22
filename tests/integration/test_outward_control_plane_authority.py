"""Shared outward identity and final truth through the authenticated application."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.outward_authorization import SequenceModelClient, approve, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("outcome", ["success", "denied", "expired", "policy_rejected"])
# Layer: integration
async def test_outward_result_uses_shared_run_and_final_truth(tmp_path, boundary, monkeypatch, outcome):
    db, inputs, calls = boundary
    if outcome == "policy_rejected":
        import orket.application.services.outward_model_tool_call_service as model_module

        model = SequenceModelClient([{"tool": "write_file", "args": {"path": "../refused.txt", "content": "refused"}}])
        monkeypatch.setattr(model_module, "create_configured_model_client", lambda **_: model)
    async with outward_api(tmp_path, inputs) as (client, context):
        body = {"run_id": "bt0-run", "task": {"description": "Shared authority", "instruction": "One approved write",
                "acceptance_contract": {"governed_tool_call": calls[0]}},
                "policy_overrides": {"approval_required_tools": ["write_file"], "approval_timeout_seconds": 10}}
        submitted = await client.post("/v1/runs", json=body)
        assert submitted.status_code == 200, submitted.text
        if outcome != "policy_rejected":
            proposal_id = submitted.json()["pending_proposals"][0]["proposal_id"]
            if outcome == "expired":
                inputs.now += timedelta(seconds=10)
            response = await client.post(f"/v1/approvals/{proposal_id}/deny", json={"reason": "declined"}) if outcome == "denied" else await approve(client, proposal_id)
            assert response.status_code == 200, response.text
        status = await client.get("/v1/runs/bt0-run")
        assert status.status_code == 200, status.text
        run = await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id="bt0-run")
        truth = await AsyncControlPlaneRecordRepository(db).get_final_truth(run_id="bt0-run")
        assert run is not None and truth is not None, "outward execution has no shared result authority"
        assert run.workload_id == "outward-governed-tools"
        assert run.current_attempt_id == "outward:bt0-run:generation:1"
        assert run.final_truth_record_id == truth.final_truth_record_id
        assert truth.result_class.value == ("success" if outcome == "success" else "blocked")
        assert status.json()["final_truth"] == truth.model_dump(mode="json")
        terminal = [event for event in await context.outward_run_event_store.list_for_run("bt0-run")
                    if event.event_type in {"run_completed", "run_failed"}]
        assert len(terminal) == 1
        assert terminal[0].payload["final_truth_record_id"] == truth.final_truth_record_id


# Layer: integration
async def test_changed_admitted_instruction_cannot_authorize_effect(tmp_path, boundary):
    _, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1])
        run = await context.outward_run_store.get("bt0-run")
        await context.outward_run_store.update(replace(run, task={**run.task, "instruction": "changed authority"}))
        response = await approve(client, proposal_id)
        assert response.status_code == 409, response.text
        assert "E_OUTWARD_AUTHORITY_INPUT_DRIFT" in response.text
        proposal = await context.outward_approval_store.get(proposal_id)
        assert proposal.status == "pending"
        assert not (tmp_path / "first.txt").exists()


# Layer: integration
async def test_prior_generation_one_requires_explicit_authority_migration(tmp_path, boundary):
    _, inputs, _ = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        old = OutwardRunRecord(run_id="old", namespace="issue:old", status="queued", submitted_at=inputs.utc_now_iso(),
            current_turn=0, max_turns=20, task={"description": "old", "instruction": "retain"}, policy_overrides={}, execution_generation=1)
        await context.outward_run_store.create(old)
        status = await client.get("/v1/runs/old")
        assert status.status_code == 200, status.text
        assert status.json()["authority_state"] == "migration_required"
        assert status.json()["final_truth"] is None
        assert await context.outward_run_store.get("old") == old
