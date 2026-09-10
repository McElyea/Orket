# Layer: integration; objective memory projection from durable SQLite iteration authority
from __future__ import annotations

from dataclasses import replace

import pytest

from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_run_control_repository import AsyncGovernedAgentRunControlRepository
from orket.application.services.governed_agent_memory_service import GovernedAgentObjectiveMemory
from orket.application.services.governed_agent_ports import GovernedAgentInvocationOutcome
from orket.application.services.governed_agent_run_control_service import GovernedAgentRunControlService
from orket.core.domain.governed_agent_continuation import decide_governed_agent_continuation
from orket_extension_sdk import AgentMemoryQueryRequest
from orket_extension_sdk.agent_fixtures import agent_iteration_request, agent_memory_query_request, prefixed_digest
from tests.integration.test_async_governed_agent_repository import (
    _binding,
    _continuation_inputs,
    _result_without_model_usage,
    _save_parent_authority,
)

pytestmark = pytest.mark.integration


async def _accepted(tmp_path):
    path = tmp_path / "agent.sqlite3"
    request = agent_iteration_request()
    binding = _binding(request)
    await _save_parent_authority(path, binding)
    repo = AsyncGovernedAgentRepository(path)
    await repo.prepare_dispatch(binding=binding, request_payload=request)
    result = _result_without_model_usage()
    proposal = result["memory_write_proposals"][0]
    proposal.update(scope="objective", role=None)
    outcome = GovernedAgentInvocationOutcome("returned", binding, result, prefixed_digest(result), None, True)
    assert (await repo.accept_result(outcome=outcome)).status == "accepted"
    return path, repo, request, binding, outcome


@pytest.mark.asyncio
@pytest.mark.parametrize("verified", [False, True])
async def test_only_verified_prior_iterations_supply_objective_memory(tmp_path, verified):
    """Layer: integration. Retained but unverified proposals cannot become advisory memory."""
    _, repo, request, binding, outcome = await _accepted(tmp_path)
    inputs = replace(_continuation_inputs(), valid_recorded_result=verified)
    await repo.publish_continuation_decision(binding=binding, accepted_result_digest=outcome.result_digest,
        decision_inputs=inputs.to_payload(), decision_payload=decide_governed_agent_continuation(inputs).to_payload())
    request["identity"].update(iteration_ordinal=2, invocation_id="invocation-2", step_id="step-2")
    next_binding = _binding(request)
    await _save_parent_authority(tmp_path / "agent.sqlite3", next_binding)
    await repo.prepare_dispatch(binding=next_binding, request_payload=request)
    query = agent_memory_query_request()
    query.update(identity=request["identity"], scope="objective", query="counted")
    memory = GovernedAgentObjectiveMemory(repo)
    entries = (await memory.query(request=AgentMemoryQueryRequest.from_wire(query))).entries
    assert len(entries) == int(verified)
    if verified:
        assert entries[0].provenance_refs == ("agent-result:invocation-1", "agent-decision:invocation-1")
    query["scope"] = "extension_private"
    with pytest.raises(ValueError, match="E_AGENT_MEMORY_SCOPE_UNADMITTED"):
        await memory.query(request=AgentMemoryQueryRequest.from_wire(query))
    query.update(scope="objective", identity={**request["identity"], "trace_id": "forged"})
    with pytest.raises(ValueError, match="E_AGENT_MEMORY_INVOCATION_UNADMITTED"):
        await memory.query(request=AgentMemoryQueryRequest.from_wire(query))


@pytest.mark.asyncio
async def test_control_arriving_after_read_prevents_stale_decision_publication(tmp_path):
    """Layer: integration. SQLite publication rejects a decision that missed an accepted control."""
    path, repo, _, binding, outcome = await _accepted(tmp_path)
    inputs = _continuation_inputs()
    controls = GovernedAgentRunControlService(AsyncGovernedAgentRunControlRepository(path))
    action = {"action_id": "operator:pause", "actor_ref": "operator:test", "command": "pause",
              "timestamp_utc": "2026-09-09T12:00:00Z", "invocation_id": binding.invocation_id}
    assert (await controls.request(binding.run_id, action))["status"] == "requested"
    publication = await repo.publish_continuation_decision(binding=binding, accepted_result_digest=outcome.result_digest,
        decision_inputs=inputs.to_payload(), decision_payload=decide_governed_agent_continuation(inputs).to_payload())
    assert publication.status == "control_changed"
    inputs = replace(inputs, accepted_pause=True, operator_action_refs=(action["action_id"],))
    publication = await repo.publish_continuation_decision(binding=binding, accepted_result_digest=outcome.result_digest,
        decision_inputs=inputs.to_payload(), decision_payload=decide_governed_agent_continuation(inputs).to_payload())
    assert publication.status == "accepted"
    assert (await controls.request(binding.run_id, {**action, "action_id": "operator:late"}))["status"] == "too_late"
