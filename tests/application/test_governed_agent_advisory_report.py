"""Report-only completion verification selected by a workload's host features."""
from __future__ import annotations

import json
from typing import Any

import pytest

from orket.application.services.governed_agent_admission import SUPPORTED_GOVERNED_AGENT_HOST_FEATURES
from orket.application.services.governed_agent_advisory_report import (
    ADVISORY_REPORT_RESPONSE_SCHEMA,
    ADVISORY_REPORT_VERIFICATION_FEATURE,
    MAX_REPORT_CHARACTERS,
    AdvisoryReportVerifier,
    fixture_advisory_report,
    is_advisory_report_schema,
    requires_advisory_report_verification,
)
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult
from orket_extension_sdk.agent_fixtures import agent_iteration_request, agent_iteration_result

pytestmark = pytest.mark.unit


def _request() -> AgentIterationRequest:
    return AgentIterationRequest.from_wire(agent_iteration_request())


def _result(proposal: Any = None, **overrides: Any) -> AgentIterationResult:
    payload = agent_iteration_result()
    payload.update(effect_proposals=[], memory_write_proposals=[], progress_claims=[])
    payload["usage"]["effect_proposals"] = 0
    if proposal is not None:
        payload["advisory_proposal"] = proposal if isinstance(proposal, str) else json.dumps(proposal)
    payload.update(overrides)
    return AgentIterationResult.from_wire(payload)


async def _verify(result: AgentIterationResult):
    return await AdvisoryReportVerifier().verify(request=_request(), result=result)


# Layer: unit
async def test_valid_report_from_supplied_sources_completes():
    observation = await _verify(_result({"report": "Two gaps.", "source_refs": ["artifact:batch-a"]}))
    assert observation.output_admissible and observation.objective_satisfied and observation.evidence_sufficient
    assert observation.authoritative_result_ref == "agent-result:invocation-1"
    assert observation.progress_projection_digest is not None
    assert observation.verifier_id == "advisory-report-verifier"


# Layer: unit
@pytest.mark.parametrize(
    "proposal",
    [
        "not json",
        {"report": "Two gaps."},
        {"report": "Two gaps.", "source_refs": ["artifact:batch-a"], "extra": 1},
        {"report": "   ", "source_refs": ["artifact:batch-a"]},
        {"report": "x" * (MAX_REPORT_CHARACTERS + 1), "source_refs": ["artifact:batch-a"]},
        {"report": "Two gaps.", "source_refs": []},
        {"report": "Two gaps.", "source_refs": ["artifact:not-supplied"]},
        {"report": "Two gaps.", "source_refs": ["artifact:batch-a", "artifact:batch-a"]},
        {"report": "Two gaps.", "source_refs": [7]},
    ],
)
async def test_malformed_or_unsourced_reports_never_complete(proposal):
    observation = await _verify(_result(proposal))
    assert not observation.output_admissible
    assert not observation.objective_satisfied
    assert observation.authoritative_result_ref is None
    assert observation.progress_projection_digest is None


# Layer: unit
async def test_a_report_that_proposes_effects_never_completes():
    payload = agent_iteration_result()
    payload["advisory_proposal"] = json.dumps({"report": "Two gaps.", "source_refs": ["artifact:batch-a"]})
    observation = await AdvisoryReportVerifier().verify(
        request=_request(), result=AgentIterationResult.from_wire(payload)
    )
    assert payload["effect_proposals"]
    assert not observation.objective_satisfied


# Layer: unit
async def test_failed_invocation_never_completes():
    result = _result(
        {"report": "Two gaps.", "source_refs": ["artifact:batch-a"]},
        invocation_status="failed", completion_recommendation="stop", normalized_reason="model_call_failed",
    )
    assert not (await _verify(result)).objective_satisfied


# Layer: unit
def test_feature_selects_advisory_verification_and_is_host_supported():
    assert ADVISORY_REPORT_VERIFICATION_FEATURE in SUPPORTED_GOVERNED_AGENT_HOST_FEATURES
    assert requires_advisory_report_verification(
        {"required_host_features": ["governed_agent_loop.v1", ADVISORY_REPORT_VERIFICATION_FEATURE]}
    )
    assert not requires_advisory_report_verification({"required_host_features": ["governed_agent_loop.v1"]})
    assert not requires_advisory_report_verification({})


# Layer: unit
def test_fixture_report_cites_every_supplied_source_and_matches_the_schema():
    response = fixture_advisory_report({"objective": {"task": "t"}, "sources": [
        {"reference": "src01", "content": {}}, {"reference": "listing", "content": {}},
    ]})
    assert response["source_refs"] == ["src01", "listing"]
    assert set(response) == set(ADVISORY_REPORT_RESPONSE_SCHEMA["required"])
    assert is_advisory_report_schema(ADVISORY_REPORT_RESPONSE_SCHEMA)
    assert not is_advisory_report_schema({"required": ["counts", "source_refs"]})
    with pytest.raises(ValueError, match="E_AGENT_FIXTURE_ADVISORY_INPUT_INVALID"):
        fixture_advisory_report({"sources": []})
