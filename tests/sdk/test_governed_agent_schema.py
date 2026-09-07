# Layer: contract

from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator, ValidationError

from orket_extension_sdk import load_governed_agent_schema
from orket_extension_sdk.agent_fixtures import (
    agent_iteration_request,
    agent_iteration_result,
    agent_model_use_receipt,
    agent_usage,
    invalid_agent_wire_fixtures,
    valid_agent_wire_payloads,
)
from orket_extension_sdk.agent_validation import (
    validate_agent_iteration_result_against_request,
    validate_governed_agent_payload,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "payload",
    list(valid_agent_wire_payloads().values()),
    ids=list(valid_agent_wire_payloads()),
)
def test_packaged_agent_schema_validates_each_v1_wire_object(payload: dict[str, object]) -> None:
    schema = load_governed_agent_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    validate_governed_agent_payload(payload)


@pytest.mark.parametrize(
    "payload",
    list(invalid_agent_wire_fixtures().values()),
    ids=list(invalid_agent_wire_fixtures()),
)
def test_shared_negative_fixtures_fail_closed(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="E_SDK_AGENT_"):
        validate_governed_agent_payload(payload)


def test_unknown_usage_keeps_counts_null_and_conservative_charges() -> None:
    receipt = agent_model_use_receipt(usage_posture="unknown")
    usage = agent_usage(usage_posture="unknown")

    validate_governed_agent_payload(receipt)
    validate_governed_agent_payload(usage)

    assert receipt["input_tokens"] is None
    assert receipt["charged_input_tokens"] == 128
    assert usage["output_tokens"] is None
    assert usage["charged_output_tokens"] == 64


def test_measured_zero_usage_is_distinct_from_unknown() -> None:
    receipt = agent_model_use_receipt()
    receipt["input_tokens"] = 0
    receipt["output_tokens"] = 0

    validate_governed_agent_payload(receipt)


def test_host_semantics_accept_matching_iteration_exchange() -> None:
    validate_agent_iteration_result_against_request(
        request=agent_iteration_request(),
        result=agent_iteration_result(),
    )


def test_host_semantics_reject_undeclared_effect_capability() -> None:
    request = agent_iteration_request()
    request["admitted_capabilities"] = ["agent.iteration.v1"]

    with pytest.raises(ValueError, match="E_HOST_AGENT_CAPABILITY_UNDECLARED"):
        validate_agent_iteration_result_against_request(
            request=request,
            result=agent_iteration_result(),
        )


def test_agent_result_schema_rejects_authoritative_completion_claim() -> None:
    payload = agent_iteration_result()
    payload["authoritative_completion"] = True

    with pytest.raises(ValidationError):
        Draft202012Validator(load_governed_agent_schema()).validate(payload)


def test_agent_schema_rejects_unknown_wire_version() -> None:
    payload = deepcopy(agent_iteration_request())
    payload["schema_version"] = "agent_iteration_request.v2"

    with pytest.raises(ValueError, match="E_SDK_AGENT_SCHEMA_INVALID"):
        validate_governed_agent_payload(payload)
