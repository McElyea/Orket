from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from orket_extension_sdk.agent_fixtures import agent_iteration_request, valid_agent_wire_payloads
from orket_extension_sdk.agent_models import (
    AgentIterationRequest,
    AgentIterationResult,
    AgentMemoryQueryRequest,
    AgentMemoryQueryResult,
    AgentModelCallRequest,
    AgentModelCallResult,
    AgentStdioFrame,
    GovernedAgentSubmission,
)
from orket_extension_sdk.agent_types import (
    AgentCancellation,
    AgentEffectProposal,
    AgentModelProfileRequest,
    AgentModelUseReceipt,
    AgentProgress,
    AgentUsage,
)

pytestmark = pytest.mark.contract

_MODELS = {
    "governed_agent_submission": GovernedAgentSubmission,
    "agent_iteration_request": AgentIterationRequest,
    "agent_iteration_result": AgentIterationResult,
    "agent_model_profile_request": AgentModelProfileRequest,
    "agent_model_call_request": AgentModelCallRequest,
    "agent_model_call_result": AgentModelCallResult,
    "agent_model_use_receipt": AgentModelUseReceipt,
    "agent_memory_query_request": AgentMemoryQueryRequest,
    "agent_memory_query_result": AgentMemoryQueryResult,
    "agent_effect_proposal": AgentEffectProposal,
    "agent_progress": AgentProgress,
    "agent_usage": AgentUsage,
    "agent_cancellation": AgentCancellation,
    "agent_stdio_frame": AgentStdioFrame,
}


@pytest.mark.parametrize("object_type", list(valid_agent_wire_payloads()))
def test_public_agent_models_round_trip_canonical_wire_payload(object_type: str) -> None:
    payload = valid_agent_wire_payloads()[object_type]
    model = _MODELS[object_type].from_wire(payload)

    assert model.to_wire() == payload


def test_public_request_is_deeply_immutable_at_json_boundaries() -> None:
    request = AgentIterationRequest.from_wire(agent_iteration_request())

    with pytest.raises(TypeError):
        request.materialized_inputs[0].content.canonical[0] = "x"  # type: ignore[index]

    thawed = request.materialized_inputs[0].content.thaw()
    thawed["task"] = "mutated copy"
    assert request.materialized_inputs[0].content.thaw()["task"] == "Count tickets by status."

    with pytest.raises((FrozenInstanceError, ValueError)):
        request.identity.run_id = "changed"  # type: ignore[misc]
