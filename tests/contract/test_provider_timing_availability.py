"""Provider observations cannot invent missing timing phases."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from orket.adapters.llm.provider_extractors import OllamaExtractor, OpenAIExtractor
from orket.application.workflows.turn_executor_runtime import runtime_tokens_payload


@pytest.mark.parametrize("extractor", [OllamaExtractor(), OpenAIExtractor()])
@pytest.mark.parametrize("reported", [{}, {"total_duration": 12_000_000}, {"eval_duration": 4_000_000}])
# Layer: contract
def test_extractors_do_not_infer_missing_phases_from_client_or_total_time(extractor, reported):
    actual = extractor.extract_timings(reported, latency_ms=999)
    expected = (None, 4.0 if "eval_duration" in reported else None,
                12.0 if "total_duration" in reported else None)
    assert actual == expected


@pytest.mark.parametrize("extractor", [OllamaExtractor(), OpenAIExtractor()])
@pytest.mark.parametrize("value", [True, False, -1, float("nan"), float("inf"), 10**400])
# Layer: contract
def test_invalid_provider_durations_stay_unavailable(extractor, value):
    payload = {name:value for name in ("prompt_eval_duration", "eval_duration", "total_duration")}
    assert extractor.extract_timings(payload, latency_ms=999) == (None, None, None)


@pytest.mark.parametrize("value", [None, True, False, -1, float("nan"), float("inf"), 10**400])
# Layer: contract
def test_turn_projection_rejects_invalid_timing_without_changing_the_observation(value):
    raw = {"timing_schema_version":"model_provider_timing.v1",
           "timings":{"prompt_ms":value, "predicted_ms":value},
           "usage":{"prompt_tokens":3,"completion_tokens":2}}
    original = deepcopy(raw)
    result = runtime_tokens_payload(SimpleNamespace(raw=raw,tokens_used=5))
    assert result["status"] == "TIMING_UNAVAILABLE"
    assert result["prompt_ms"] is None and result["predicted_ms"] is None
    assert result["timing_posture"] == "unavailable"
    assert raw == original


# Layer: contract
def test_historical_numeric_timings_keep_their_unverified_provenance():
    raw = {"timings":{"prompt_ms":0.0,"predicted_ms":12.0}}
    result = runtime_tokens_payload(SimpleNamespace(raw=raw,tokens_used=5))
    assert result["timing_posture"] == "legacy_unverified"
    assert result["timing_schema_version"] is None
    assert raw == {"timings":{"prompt_ms":0.0,"predicted_ms":12.0}}


@pytest.mark.parametrize("extractor", [OllamaExtractor(), OpenAIExtractor()])
# Layer: contract
def test_reported_zero_and_fractional_phases_remain_distinct_from_missing_total(extractor):
    assert extractor.extract_timings({"prompt_eval_duration":0,"eval_duration":500_000},latency_ms=999) == (0.0,0.5,None)
