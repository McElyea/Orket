"""Governed model latency must survive the host/SDK boundary without invented zero."""
from __future__ import annotations

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.application.services.governed_agent_broker_service import GovernedAgentResolvedModelProfile, _model_result
from orket.application.services.governed_agent_model_provider import _observation
from orket_extension_sdk import AgentModelCallRequest, AgentModelCallResult
from orket_extension_sdk.agent_fixtures import agent_model_call_request

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("latency,expected", [(None, None), (False, None), (True, None),
    (-1, None), ("12", None), (float("nan"), None), (0, 0), (17, 17)])
@pytest.mark.parametrize("content,returned", [('{"counts":{"open":2}}', True), ('invalid JSON', False)])
# Layer: contract
def test_model_latency_survives_observation_receipt_and_wire(latency, expected, content, returned):
    observation = _observation(ModelResponse(content=content, raw={
        "input_tokens": 12, "output_tokens": 4, "latency_ms": latency,
    }), response_mode="json")
    assert observation.latency_ms == expected
    request = AgentModelCallRequest.from_wire(agent_model_call_request())
    profile = GovernedAgentResolvedModelProfile(
        requested_profile_ref="local.planner", resolved_profile_ref="local.planner",
        provider="llama_cpp", provider_version=None, model="fixture", model_digest=None,
    )
    result, charged_input, charged_output = _model_result(request, profile, observation)
    wire = result.to_wire()
    receipt = wire["receipt"]
    assert receipt["latency_ms"] == expected
    assert receipt["latency_posture"] == ("reported" if expected is not None else "unavailable")
    assert receipt["schema_version"] == "agent_model_use_receipt.v2"
    assert receipt["status"] == ("returned" if returned else "failed")
    assert (charged_input, charged_output) == (12, 4)
    assert AgentModelCallResult.from_wire(wire).to_wire() == wire


@pytest.mark.parametrize("input_tokens,output_tokens", [(None, 4), (12, None), (False, 4), (12, True)])
# Layer: contract
def test_partial_or_invalid_token_metadata_retains_unknown_usage(input_tokens, output_tokens):
    observation = _observation(ModelResponse(content='{"counts":{}}', raw={
        "input_tokens": input_tokens, "output_tokens": output_tokens,
    }), response_mode="json")
    request = AgentModelCallRequest.from_wire(agent_model_call_request())
    profile = GovernedAgentResolvedModelProfile(
        requested_profile_ref="local.planner", resolved_profile_ref="local.planner",
        provider="llama_cpp", provider_version=None, model="fixture", model_digest=None,
    )
    result, charged_input, charged_output = _model_result(request, profile, observation)
    assert result.receipt.usage_posture == "unknown"
    assert result.receipt.input_tokens is None and result.receipt.output_tokens is None
    assert (charged_input, charged_output) == (request.max_input_tokens, request.max_output_tokens)
    assert result.receipt.latency_ms is None
