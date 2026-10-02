from __future__ import annotations

from dataclasses import replace

import pytest

from orket.reforger.proof_slices import phase0_adapt_request, phase0_baseline_request
from orket.reforger.service_contracts import (
    SERVICE_MODE_ADAPT,
    AcceptanceThresholds,
    BaselineMetrics,
    CandidateSummary,
    ExternalConsumerVerdict,
    PromptReforgerServiceRequest,
    PromptReforgerServiceResult,
)


@pytest.mark.contract
def test_bounded_adapt_requires_candidate_budget() -> None:
    payload = phase0_adapt_request().to_payload()
    payload.pop("candidate_budget", None)

    with pytest.raises(ValueError, match="candidate_budget is required"):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
def test_phase0_request_roundtrip_preserves_contract_fields() -> None:
    baseline = PromptReforgerServiceRequest.from_payload(phase0_baseline_request().to_payload())
    adapt = PromptReforgerServiceRequest.from_payload(phase0_adapt_request().to_payload())

    assert baseline.to_payload() == phase0_baseline_request().to_payload()
    assert adapt.to_payload() == phase0_adapt_request().to_payload()
    assert adapt.service_mode == SERVICE_MODE_ADAPT
    assert adapt.candidate_budget == 4


@pytest.mark.contract
@pytest.mark.parametrize("field,value,diagnostic", [
    ("request_id", " ", "request_id must be non-empty"),
    ("service_mode", "invented", "service_mode must be one of"),
    ("bridge_contract_ref", "", "bridge_contract_ref must be non-empty"),
    ("eval_slice_ref", "", "eval_slice_ref must be non-empty"),
    ("runtime_context", [], "runtime_context must be an object"),
    ("acceptance_thresholds", [], "acceptance_thresholds must be an object"),
    ("baseline_bundle_ref", None, "exactly one of baseline"),
    ("baseline_prompt_ref", "prompt", "exactly one of baseline"),
    ("candidate_budget", -1, "must be non-negative"),
])
def test_request_rejects_missing_identity_or_ambiguous_baseline(field, value, diagnostic):
    payload = phase0_baseline_request().to_payload()
    payload[field] = value
    with pytest.raises(ValueError, match=diagnostic):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("value", [None, [], "request"])
def test_request_refuses_non_object_root(value):
    with pytest.raises(ValueError, match="payload must be an object"):
        PromptReforgerServiceRequest.from_payload(value)


@pytest.mark.contract
@pytest.mark.parametrize("value", [2.5, "2.5", "bad", " ", [], {}])
def test_candidate_budget_cannot_be_fractional_or_unparseable(value):
    payload = phase0_adapt_request().to_payload()
    payload["candidate_budget"] = value
    with pytest.raises(ValueError, match="candidate_budget must be an integer"):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("value", [0, -1])
def test_adaptation_requires_a_positive_candidate_budget(value):
    payload = phase0_adapt_request().to_payload()
    payload["candidate_budget"] = value
    with pytest.raises(ValueError, match="greater than zero"):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("budget", [4.0, " 4 "])
def test_request_normalizes_numeric_and_optional_transport_values(budget):
    payload = phase0_adapt_request().to_payload()
    payload.update(request_id=" /customer:trial/ ", candidate_budget=budget, consumer_id=" ",
                   baseline_bundle_ref=None, baseline_prompt_ref=" prompt://baseline ")
    payload["runtime_context"].update(runtime_version=" 1.0 ", endpoint_id=" endpoint ", quantization=" q8 ")
    payload["acceptance_thresholds"] = {"certified_min_score": " 1 ", "certified_with_limits_min_score": " .85 "}
    request = PromptReforgerServiceRequest.from_payload(payload)
    result = request.to_payload()
    assert result["candidate_budget"] == 4 and request.artifact_token == "customer-trial"
    assert "consumer_id" not in result and "baseline_bundle_ref" not in result
    assert result["baseline_prompt_ref"] == "prompt://baseline"
    assert result["runtime_context"] == {**payload["runtime_context"], "runtime_version": "1.0",
                                         "endpoint_id": "endpoint", "quantization": "q8"}
    assert result["acceptance_thresholds"] == {"certified_min_score": 1., "certified_with_limits_min_score": .85}
    assert replace(request, request_id="???").artifact_token == "service-run"


@pytest.mark.contract
@pytest.mark.parametrize("value", [None, [], " ", "bad"])
def test_acceptance_thresholds_refuse_non_numeric_values(value):
    payload = phase0_baseline_request().to_payload()
    payload["acceptance_thresholds"]["certified_min_score"] = value
    with pytest.raises(ValueError, match="certified_min_score must be numeric"):
        PromptReforgerServiceRequest.from_payload(payload)


@pytest.mark.contract
@pytest.mark.parametrize("certified,limited,diagnostic", [
    (-.1, 0, "certified_min_score must be within"),
    (1.1, 0, "certified_min_score must be within"),
    (1, -.1, "certified_with_limits_min_score must be within"),
    (1, 1.1, "certified_with_limits_min_score must be within"),
    (.8, .9, "must not exceed"),
])
def test_threshold_order_and_bounds_are_enforced(certified, limited, diagnostic):
    with pytest.raises(ValueError, match=diagnostic):
        AcceptanceThresholds(certified, limited)


def _result():
    request = phase0_baseline_request()
    return PromptReforgerServiceResult(request_id=request.request_id, service_run_id="run",
        result_class="certified", observed_path="primary", observed_result="success",
        runtime_context=request.runtime_context, bridge_contract_ref=request.bridge_contract_ref,
        eval_slice_ref=request.eval_slice_ref, baseline_metrics=BaselineMetrics(.987654321, 0, 1),
        candidate_summary=CandidateSummary(1, "winner", .987654321), acceptance_reason="receipt verified",
        bundle_ref="bundle://result", known_limits=("fixture",), requalification_triggers=("model change",))


@pytest.mark.contract
@pytest.mark.parametrize("field,value,diagnostic", [
    ("request_id", "", "request_id must be non-empty"),
    ("service_run_id", "", "service_run_id must be non-empty"),
    ("result_class", "passed", "result_class must be one of"),
    ("observed_path", "assumed", "observed_path must be one of"),
    ("observed_result", "probably", "observed_result must be one of"),
    ("acceptance_reason", " ", "acceptance_reason must be non-empty"),
    ("result_class", "unsupported", "unsupported results must not carry bundle_ref"),
])
def test_result_cannot_claim_an_unsupported_class_or_bundle(field, value, diagnostic):
    with pytest.raises(ValueError, match=diagnostic):
        replace(_result(), **{field: value})


@pytest.mark.contract
def test_result_payload_preserves_limits_and_omits_unavailable_winner():
    result = _result().to_payload()
    assert result["known_limits"] == ["fixture"] and result["requalification_triggers"] == ["model change"]
    assert result["candidate_summary"] == {"evaluated_candidate_count": 1, "winning_candidate_id": "winner",
                                           "winning_score": .987654}
    assert result["baseline_metrics"] == {"score": .987654, "hard_fail_count": 0, "soft_fail_count": 1}
    unsupported = replace(_result(), result_class="unsupported", bundle_ref=None,
                          candidate_summary=CandidateSummary(0)).to_payload()
    assert "bundle_ref" not in unsupported
    assert unsupported["candidate_summary"] == {"evaluated_candidate_count": 0}


@pytest.mark.contract
@pytest.mark.parametrize("field,value,diagnostic", [
    ("consumer_id", "", "consumer_id must be non-empty"),
    ("verdict_class", "passed", "verdict_class must be one of"),
    ("verdict_source", "guessed", "verdict_source must be one of"),
    ("service_result_ref", "", "service_result_ref must be non-empty"),
])
def test_consumer_verdict_requires_identity_source_and_result_reference(field, value, diagnostic):
    payload = {"consumer_id": "consumer", "verdict_class": "certified", "verdict_source": "service_adopted",
               "service_result_ref": "result://run"}
    assert ExternalConsumerVerdict(**payload).to_payload() == payload
    with pytest.raises(ValueError, match=diagnostic):
        ExternalConsumerVerdict(**{**payload, field: value})
