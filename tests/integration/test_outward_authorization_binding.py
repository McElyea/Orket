"""Layer: integration. Binding, drift refusal and protected persisted authority."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import aiosqlite
import pytest

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from tests.helpers.outward_authorization import approve, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary


@pytest.mark.integration
@pytest.mark.parametrize("drift", ["arguments", "namespace", "generation", "turn", "step", "run-policy", "connector-version", "allowlist", "workspace"])
# Layer: integration
async def test_approved_binding_refuses_changed_dispatch_inputs(tmp_path, boundary, drift):
    """Layer: integration. Mutating current run/config after approval cannot change the authorized effect."""
    _db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1])
        await context.outward_approval_service.approve(proposal_id, operator_ref="operator:fixture")
        run = await context.outward_run_store.get("bt0-run")
        connector = context.outward_run_execution_service.connector_service
        if drift == "arguments":
            task = deepcopy(run.task)
            task["_outward_execution_state"]["model_tool_calls"][-1]["args"]["content"] = "unapproved"
            run = replace(run, task=task)
        elif drift in {"namespace", "generation", "turn"}:
            field, value = {"namespace": ("namespace", "changed"), "generation": ("execution_generation", 2), "turn": ("current_turn", 2)}[drift]
            run = replace(run, **{field: value})
        elif drift == "step":
            task = deepcopy(run.task)
            task["_outward_execution_state"]["step_index"] = 9
            run = replace(run, task=task)
        elif drift == "run-policy":
            run = replace(run, policy_overrides={**run.policy_overrides, "approval_required_tools": []})
        elif drift == "connector-version":
            connector.connector_registry = BuiltInConnectorRegistry([
                replace(connector.connector_registry.get("write_file"), contract_version="changed.v2"),
            ])
        elif drift == "allowlist":
            connector.executor.http_allowlist = ("changed.invalid",)
        elif drift == "workspace":
            connector.executor.workspace_root = tmp_path / "changed"
        await context.outward_run_store.update(run)
        response = await approve(client, proposal_id)
        assert response.status_code == 409, response.text
        expected = "E_OUTWARD_AUTHORITY_INPUT_DRIFT" if drift in {"namespace", "generation", "run-policy"} else "E_OUTWARD_AUTHORIZATION_"
        assert expected in response.text
        async with context.outward_approval_service.unit_of_work.transaction() as transaction:
            assert await transaction.effects.get(f"outward-effect:{proposal_id}") is None
        events = await context.outward_run_event_store.list_for_run("bt0-run")
        assert not any(event.event_type == "tool_invoked" for event in events)
    assert not (tmp_path / "first.txt").exists()


@pytest.mark.integration
# Layer: integration
async def test_original_binding_is_protected_and_dispatches_after_admitted_approval_deadline(tmp_path, boundary):
    """Layer: integration. Retained full args stay private, immutable, and usable after approval admission."""
    db_path, inputs, calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls[:1], approval_seconds=10)
        proposal = await context.outward_approval_store.get(proposal_id)
        assert proposal.authorization.arguments == calls[0]["args"]
        assert proposal.authorization.execution_generation == 1
        review = await client.get(f"/v1/approvals/{proposal_id}")
        assert calls[0]["args"]["content"] not in review.text
        assert "authorization_json" not in review.json()
        async with connect_sqlite_wal(db_path) as conn:
            with pytest.raises(aiosqlite.IntegrityError, match="E_OUTWARD_AUTHORIZATION_IMMUTABLE"):
                await conn.execute("UPDATE outward_approval_proposals_v2 SET authorization_json = '{}' WHERE proposal_id = ?", (proposal_id,))
            with pytest.raises(aiosqlite.IntegrityError, match="E_OUTWARD_PROPOSAL_IMMUTABLE"):
                await context.outward_approval_store.save(proposal, connection=conn)
        await context.outward_approval_service.approve(proposal_id, operator_ref="operator:fixture")
        inputs.now += timedelta(hours=1)
        response = await approve(client, proposal_id)
        assert response.status_code == 200, response.text
    assert (tmp_path / "first.txt").read_text() == calls[0]["args"]["content"]
