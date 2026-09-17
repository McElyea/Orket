"""Real durable broker reuse and child IPC across receipt versions."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from orket.adapters.llm.local_model_provider import ModelResponse
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_model_provider import _observation
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk import AgentModelCallRequest
from orket_extension_sdk.agent_fixtures import agent_model_call_request, agent_model_call_result, prefixed_digest
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    agent_request,
    binding_for,
    prepare_authority,
    resolved_profiles,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _MissingLatencyProvider:
    def __init__(self):
        self.calls = 0

    async def call(self, *, request, profile):
        self.calls += 1
        return _observation(ModelResponse(content='{"counts":{"open":2}}', raw={
            "input_tokens": 12, "output_tokens": 4,
        }), response_mode="json")


def _broker(repository, provider):
    return GovernedAgentHostBroker(iteration_repository=repository, call_repository=repository,
                                   model_provider=provider, model_profiles=resolved_profiles())


@pytest.mark.parametrize("legacy", [False, True])
# Layer: integration
async def test_broker_restart_preserves_v1_or_v2_receipt_without_repeat_inference(tmp_path, legacy):
    request = agent_request()
    binding = binding_for(request)
    database = tmp_path / "calls.sqlite3"
    repository = await prepare_authority(database, request, binding)
    provider = _MissingLatencyProvider()
    call = AgentModelCallRequest.from_wire(agent_model_call_request()).to_wire()
    if legacy:
        reservation = await repository.reserve_call(binding=binding, operation="model.call.v1",
            call_id=call["call_id"], role=call["role"], request_digest=prefixed_digest(call),
            reserved_input_tokens=call["max_input_tokens"], reserved_output_tokens=call["max_output_tokens"])
        assert reservation.status == "prepared"
        fixture = Path(__file__).parents[1] / "fixtures/governed_agent/model_receipt_v1.json"
        retained = agent_model_call_result()
        retained["receipt"] = json.loads(await asyncio.to_thread(fixture.read_text, encoding="utf-8"))
        await repository.complete_call(binding=binding, call_id=call["call_id"], request_digest=prefixed_digest(call),
            result_payload=retained, result_digest=prefixed_digest(retained), charged_input_tokens=128,
            charged_output_tokens=64)
    else:
        retained = await _broker(repository, provider).dispatch_call(
            binding=binding, operation="model.call.v1", call_payload=call)
        assert retained["receipt"]["latency_ms"] is None
        assert retained["receipt"]["latency_posture"] == "unavailable"
        assert retained["receipt"]["schema_version"] == "agent_model_use_receipt.v2"
    before = await repository.list_call_records(invocation_id=binding.invocation_id)
    restarted = AsyncGovernedAgentRepository(database)
    returned = await _broker(restarted, provider).dispatch_call(
        binding=binding, operation="model.call.v1", call_payload=call)
    assert returned == retained
    assert provider.calls == (0 if legacy else 1)
    assert await restarted.list_call_records(invocation_id=binding.invocation_id) == before


# Layer: integration
async def test_real_child_retains_unavailable_latency_in_durable_host_receipts(tmp_path):
    request = agent_request()
    binding = binding_for(request)
    repository = await prepare_authority(tmp_path / "child.sqlite3", request, binding)
    provider = DeterministicModelProvider()
    invoker = GovernedAgentSubprocessInvoker(extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent", allowed_stdlib_modules=("json",),
        broker=_broker(repository, provider))
    outcome = await invoker.invoke_once(binding=binding, request_payload=request)
    assert outcome.status == "returned", (outcome.normalized_reason, invoker.last_diagnostic_tail)
    assert outcome.child_confirmed_stopped
    receipts = outcome.result_payload["model_receipts"]
    assert len(receipts) == 3
    assert all(receipt["schema_version"] == "agent_model_use_receipt.v2" and receipt["latency_ms"] is None
               and receipt["latency_posture"] == "unavailable" for receipt in receipts)
    records = await repository.list_call_records(invocation_id=binding.invocation_id)
    assert len(records) == 3 and all(record.status == "completed" for record in records)
    assert (await repository.accept_result(outcome=outcome)).status == "accepted"


# Layer: integration
async def test_old_ready_peer_is_refused_before_model_reservation(tmp_path, monkeypatch):
    request = agent_request()
    binding = binding_for(request)
    repository = await prepare_authority(tmp_path / "old-peer.sqlite3", request, binding)
    provider = _MissingLatencyProvider()
    child = Path(__file__).parents[1] / "fixtures/governed_agent/legacy_ready_child.py"
    call = AgentModelCallRequest.from_wire(agent_model_call_request()).to_wire()
    invoker = GovernedAgentSubprocessInvoker(extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent", allowed_stdlib_modules=("json",),
        broker=_broker(repository, provider))

    async def launch_legacy_peer():
        return await asyncio.create_subprocess_exec(sys.executable, "-I", str(child), json.dumps(call),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            cwd=tmp_path, start_new_session=sys.platform != "win32")

    monkeypatch.setattr(invoker, "_start_child", launch_legacy_peer)
    outcome = await invoker.invoke_once(binding=binding, request_payload=request)
    assert outcome.normalized_reason == "E_AGENT_READY_FEATURE_MISMATCH"
    assert outcome.child_confirmed_stopped
    assert provider.calls == 0
    assert await repository.list_call_records(invocation_id=binding.invocation_id) == ()
