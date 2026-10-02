"""Real SQLite broker authority with explicit controlled model/memory providers."""
from copy import deepcopy
from dataclasses import replace

import pytest

from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentHostBroker,
    GovernedAgentMemoryObservation,
    GovernedAgentModelObservation,
)
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket_extension_sdk import AgentMemoryEntry
from orket_extension_sdk.agent_fixtures import (
    agent_memory_query_request,
    agent_memory_query_result,
    agent_model_call_request,
)
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority, resolved_profiles

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class ControlledProvider:
    def __init__(self, *, observation=None, failure=None, entries=()):
        self.observation = observation
        self.failure = failure
        self.entries = entries
        self.calls = 0

    async def call(self, *, request, profile):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return self.observation

    async def query(self, *, request):
        self.calls += 1
        return GovernedAgentMemoryObservation(self.entries)


def _observation(**changes):
    values = dict(response={"counts": {}}, usage_posture="measured", input_tokens=2, output_tokens=1,
        estimate_source=None, latency_ms=1, finish_reason="stop")
    return GovernedAgentModelObservation(**{**values, **changes})


async def _broker(root, provider, *, profiles=None, memory=None, admit_memory=False):
    request = agent_request()
    if admit_memory:
        request["admitted_capabilities"].append("memory.query")
    binding = binding_for(request)
    repository = await prepare_authority(root / "authority.sqlite3", request, binding)
    broker = GovernedAgentHostBroker(iteration_repository=repository, call_repository=repository,
        model_provider=provider, model_profiles=resolved_profiles() if profiles is None else profiles,
        memory_provider=memory)
    return broker, repository, binding


async def _records(repository, binding):
    # Observe committed state through a newly constructed repository/connection owner.
    return await AsyncGovernedAgentRepository(repository.db_path).list_call_records(invocation_id=binding.invocation_id)


@pytest.mark.parametrize("changes,profile_changes,error", [
    ({"role": "unadmitted"}, {}, "MODEL_ROLE_UNADMITTED"),
    ({"profile_ref": "other"}, {}, "MODEL_PROFILE_MISMATCH"),
    ({"max_input_tokens": 4097}, {}, "MODEL_PROFILE_LIMIT_EXCEEDED"),
    ({"max_output_tokens": 1025}, {}, "MODEL_PROFILE_LIMIT_EXCEEDED"),
    ({"timeout_ms": 15001}, {}, "MODEL_PROFILE_LIMIT_EXCEEDED"),
    ({"response_mode": "text"}, {}, "MODEL_PROFILE_LIMIT_EXCEEDED"),
    ({"streaming_preference": "required"}, {}, "MODEL_PROFILE_LIMIT_EXCEEDED"),
    ({}, {"requested_profile_ref": "other"}, "MODEL_PROFILE_UNAVAILABLE"),
    ({}, {"supports_json": False}, "MODEL_JSON_UNSUPPORTED"),
    ({"response_schema": []}, {}, "SDK_AGENT_SCHEMA_INVALID"),
    ({"response_schema": {"type": "invalid-type"}}, {}, "MODEL_RESPONSE_SCHEMA_INVALID"),
])
async def test_admission_refuses_before_reservation_or_provider(tmp_path, changes, profile_changes, error):
    profiles = resolved_profiles()
    profiles["local.planner"] = replace(profiles["local.planner"], **profile_changes)
    provider = ControlledProvider(observation=_observation())
    broker, repository, binding = await _broker(tmp_path, provider, profiles=profiles)
    call = {**agent_model_call_request(), **changes}
    before = deepcopy(call)
    expected_code = "E_" + error if error.startswith("SDK_") else "E_AGENT_" + error
    with pytest.raises(ValueError, match=expected_code):
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    assert call == before and provider.calls == 0 and await _records(repository, binding) == ()


async def test_stale_binding_and_foreign_call_identity_cannot_reserve(tmp_path):
    provider = ControlledProvider(observation=_observation())
    broker, repository, binding = await _broker(tmp_path, provider)
    call = agent_model_call_request()
    with pytest.raises(ValueError, match="E_AGENT_BROKER_BINDING_STALE"):
        await broker.dispatch_call(binding=replace(binding, invocation_id="unknown"), operation="model.call.v1", call_payload=call)
    call["identity"]["run_id"] = "other"
    with pytest.raises(ValueError, match="E_AGENT_BROKER_CALL_IDENTITY_MISMATCH"):
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    assert provider.calls == 0 and await _records(repository, binding) == ()


@pytest.mark.parametrize("changes,error", [
    ({"usage_posture": "unknown"}, "MODEL_UNKNOWN_USAGE_HAS_COUNTS"),
    ({"input_tokens": None}, "MODEL_KNOWN_USAGE_MISSING_COUNTS"),
    ({"input_tokens": 4097}, "MODEL_OBSERVED_USAGE_EXCEEDED"),
    ({"status": "failed"}, "MODEL_FAILED_REASON_REQUIRED"),
])
async def test_invalid_provider_observation_retains_uncertain_call_without_receipt(tmp_path, changes, error):
    provider = ControlledProvider(observation=_observation(**changes))
    broker, repository, binding = await _broker(tmp_path, provider)
    call = agent_model_call_request()
    with pytest.raises(ValueError, match="E_AGENT_" + error):
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    retained, = await _records(repository, binding)
    assert retained.status == "uncertain" and retained.result_payload is None
    assert retained.reserved_input_tokens == 4096 and retained.charged_input_tokens == 0
    with pytest.raises(ValueError, match="E_AGENT_BROKER_RESERVATION_UNCERTAIN"):
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    assert provider.calls == 1 and await _records(repository, binding) == (retained,)


@pytest.mark.parametrize("failure,reason", [
    (ModelConnectionError("controlled"), "E_AGENT_MODEL_PROVIDER_UNAVAILABLE"),
    (ModelTimeoutError("controlled"), "E_AGENT_MODEL_PROVIDER_TIMEOUT"),
    (ModelProviderError("controlled"), "E_AGENT_MODEL_PROVIDER_UNCERTAIN"),
])
async def test_provider_failure_is_durably_uncertain_and_keeps_cause(tmp_path, failure, reason):
    provider = ControlledProvider(failure=failure)
    broker, repository, binding = await _broker(tmp_path, provider)
    with pytest.raises(ValueError, match=reason) as observed:
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=agent_model_call_request())
    assert observed.value.__cause__ is failure
    retained, = await _records(repository, binding)
    assert retained.status == "uncertain" and retained.result_payload is None and provider.calls == 1


@pytest.mark.parametrize("changes,status,reason,charge", [
    ({"usage_posture": "unknown", "input_tokens": None, "output_tokens": None}, "returned", None, 4096),
    ({"response": {"missing": "counts"}}, "failed", "model_response_contract_failed", 2),
    ({"status": "timed_out", "normalized_reason": "controlled-timeout"}, "timed_out", "controlled-timeout", 2),
])
async def test_observed_result_and_usage_are_retained_across_idempotent_dispatch(tmp_path, changes, status, reason, charge):
    provider = ControlledProvider(observation=_observation(**changes))
    broker, repository, binding = await _broker(tmp_path, provider)
    call = agent_model_call_request()
    result = await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    assert result["receipt"]["status"] == status and result["normalized_reason"] == reason
    assert result["receipt"]["charged_input_tokens"] == charge
    if status != "returned":
        assert result["response"] is None and result["response_digest"] is None
    retained, = await _records(repository, binding)
    assert retained.status == "completed" and retained.charged_input_tokens == charge
    assert retained.result_payload == result
    assert await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call) == result
    call["messages"][0]["content"] = "changed after completion"
    with pytest.raises(ValueError, match="E_AGENT_BROKER_RESERVATION_CONFLICT"):
        await broker.dispatch_call(binding=binding, operation="model.call.v1", call_payload=call)
    assert provider.calls == 1 and await _records(repository, binding) == (retained,)


@pytest.mark.parametrize("admitted", [False, True])
async def test_memory_unavailable_is_either_unadmitted_or_retained_blocked_result(tmp_path, admitted):
    provider = ControlledProvider(observation=_observation())
    broker, repository, binding = await _broker(tmp_path, provider, admit_memory=admitted)
    call = agent_memory_query_request()
    if not admitted:
        with pytest.raises(ValueError, match="E_AGENT_MEMORY_CAPABILITY_UNADMITTED"):
            await broker.dispatch_call(binding=binding, operation="memory.query.v1", call_payload=call)
        assert await _records(repository, binding) == ()
    else:
        result = await broker.dispatch_call(binding=binding, operation="memory.query.v1", call_payload=call)
        assert result["status"] == "blocked" and result["normalized_reason"] == "memory_provider_unavailable"
        assert result["entries"] == []
        assert await broker.dispatch_call(binding=binding, operation="memory.query.v1", call_payload=call) == result
        retained, = await _records(repository, binding)
        assert retained.status == "completed" and retained.result_payload == result
    assert provider.calls == 0


@pytest.mark.parametrize("limit,error", [("max_items", "ITEM"), ("max_content_bytes", "CONTENT")])
async def test_memory_over_budget_never_publishes_completed_receipt(tmp_path, limit, error):
    entry = AgentMemoryEntry.model_validate(agent_memory_query_result()["entries"][0])
    memory = ControlledProvider(entries=(entry, replace_entry(entry)))
    provider = ControlledProvider(observation=_observation())
    broker, repository, binding = await _broker(tmp_path, provider, memory=memory, admit_memory=True)
    call = agent_memory_query_request()
    call[limit] = 1
    with pytest.raises(ValueError, match=f"E_AGENT_MEMORY_{error}_BUDGET_EXCEEDED"):
        await broker.dispatch_call(binding=binding, operation="memory.query.v1", call_payload=call)
    retained, = await _records(repository, binding)
    assert retained.status == "reserved" and retained.result_payload is None
    with pytest.raises(ValueError, match="E_AGENT_BROKER_RESERVATION_UNCERTAIN"):
        await broker.dispatch_call(binding=binding, operation="memory.query.v1", call_payload=call)
    assert memory.calls == 1 and provider.calls == 0


def replace_entry(entry):
    return AgentMemoryEntry.model_validate({**entry.model_dump(), "reference": "memory:2"})
