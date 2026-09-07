from __future__ import annotations

import pytest

from orket_extension_sdk.agent_fixtures import agent_model_call_request, agent_model_call_result
from orket_extension_sdk.agent_models import AgentModelCallRequest, AgentModelCallResult
from orket_extension_sdk.agent_testing import (
    ScriptedAgentModelCapability,
    assert_canonical_agent_payload_equal,
    ticket_report_fixture,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_scripted_model_capability_records_matching_call() -> None:
    request = AgentModelCallRequest.from_wire(agent_model_call_request())
    expected = AgentModelCallResult.from_wire(agent_model_call_result())
    capability = ScriptedAgentModelCapability([expected])

    actual = await capability.call(request)

    assert actual == expected
    assert capability.requests == [request]


def test_ticket_report_fixture_is_fresh_and_has_expected_totals() -> None:
    first = ticket_report_fixture()
    second = ticket_report_fixture()
    first["expected_report"]["counts"]["open"] = 99

    assert second["expected_report"]["counts"]["open"] == 2
    assert_canonical_agent_payload_equal(second, ticket_report_fixture())
