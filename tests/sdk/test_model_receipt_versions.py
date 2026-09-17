"""Versioned receipt reads and explicit admission for the new timing contract."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket_extension_sdk import AgentIterationResult, AgentModelCallResult, AgentModelUseReceipt, AgentStdioFrame
from orket_extension_sdk.agent_fixtures import (
    agent_broker_frame,
    agent_iteration_result,
    agent_model_call_result,
    agent_model_use_receipt,
)
from orket_extension_sdk.agent_validation import validate_governed_agent_payload
from orket_extension_sdk.manifest import AgentWorkloadDeclaration

pytestmark = pytest.mark.contract


# Layer: contract
def test_historical_v1_receipts_roundtrip_without_new_fields():
    path = Path(__file__).parents[1] / "fixtures/governed_agent/model_receipt_v1.json"
    historical = json.loads(path.read_text(encoding="utf-8"))
    assert AgentModelUseReceipt.from_wire(historical).to_wire() == historical
    call = agent_model_call_result()
    call["receipt"] = historical
    assert AgentModelCallResult.from_wire(call).to_wire() == call
    iteration = agent_iteration_result()
    iteration["model_receipts"] = [historical]
    assert AgentIterationResult.from_wire(iteration).to_wire() == iteration


@pytest.mark.parametrize("version,latency,posture", [
    ("agent_model_use_receipt.v1", None, None),
    ("agent_model_use_receipt.v1", 0, "reported"),
    ("agent_model_use_receipt.v2", None, "reported"),
    ("agent_model_use_receipt.v2", 0, "unavailable"),
    ("agent_model_use_receipt.v2", True, "reported"),
    ("agent_model_use_receipt.v2", 0, None),
])
# Layer: contract
def test_schema_rejects_invalid_latency_and_posture(version, latency, posture):
    receipt = agent_model_use_receipt()
    receipt.update(schema_version=version, latency_ms=latency)
    if posture is None:
        receipt.pop("latency_posture")
    else:
        receipt["latency_posture"] = posture
    with pytest.raises(ValueError, match="E_SDK_AGENT_SCHEMA_INVALID"):
        validate_governed_agent_payload(receipt)
    with pytest.raises(ValueError):
        AgentModelUseReceipt.from_wire(receipt)


# Layer: contract
def test_new_agent_declaration_requires_nullable_receipt_feature():
    with pytest.raises(ValueError, match="E_SDK_AGENT_HOST_FEATURE_REQUIRED.*agent_model_use_receipt.v2"):
        AgentWorkloadDeclaration(
            contract_version="governed_agent_loop.v1",
            required_host_features=["governed_agent_loop.v1", "agent_stdio_ipc.v1"],
            model_profiles=[{"role": "planner", "profile_ref": "local.planner"}],
            resource_requirements={"max_model_calls_per_iteration": 2},
        )


# Layer: contract
def test_ready_frames_preserve_history_and_type_new_receipt_support():
    frame = agent_broker_frame()
    frame.update(direction="child_to_parent", message_type="ready", payload={
        "supported_protocol_versions": ["agent_stdio_ipc.v1"],
        "supported_contract_versions": ["governed_agent_loop.v1"],
    })
    assert AgentStdioFrame.from_wire(frame).to_wire() == frame
    frame["payload"]["supported_model_receipt_versions"] = ["agent_model_use_receipt.v2"]
    assert AgentStdioFrame.from_wire(frame).to_wire() == frame
    for invalid in (None, True, [], "agent_model_use_receipt.v2", [None], [""]):
        frame["payload"]["supported_model_receipt_versions"] = invalid
        with pytest.raises(ValueError, match="E_SDK_AGENT_READY_PAYLOAD_INVALID"):
            AgentStdioFrame.from_wire(frame)
