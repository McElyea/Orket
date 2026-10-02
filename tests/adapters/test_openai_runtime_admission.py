"""Provider wire-value contracts only; no transport or actual inference proof."""
from copy import deepcopy

import pytest

from orket.adapters.llm.openai_compat_runtime import (
    extract_openai_content,
    extract_openai_timings,
    extract_openai_tool_calls,
    extract_openai_usage,
    normalize_openai_base_url,
    recover_structured_reasoning_answer,
    validate_openai_messages,
)

pytestmark = pytest.mark.contract


def _payload(**message):
    return {"choices": [{"message": message}]}


@pytest.mark.parametrize("payload,expected", [
    ({"choices": [None]}, None), (_payload(content=42), None),
    (_payload(content=["not an object"]), None), (_payload(content=[{}]), ""),
    (_payload(content=[{"text": "first"}, {}, {"text": " second"}]), "first second"),
    (_payload(content="", reasoning_content=[{"text": 42}]), None),
    (_payload(content=None, reasoning_content=[{"text": "fallback"}]), "fallback"),
])
def test_content_shape_and_empty_values_remain_distinguishable(payload, expected):
    before = deepcopy(payload)
    assert extract_openai_content(payload) == expected
    assert payload == before


@pytest.mark.parametrize("payload,expected", [
    ({}, []), ({"choices": []}, []), ({"choices": [None]}, []), ({"choices": [{"message": []}]}, []),
    (_payload(tool_calls={}), []),
    (_payload(tool_calls=[None, {"id": "retained", "function": {}}, "ignored"]), [{"id": "retained", "function": {}}]),
])
def test_tool_call_extraction_filters_shape_without_claiming_argument_validation(payload, expected):
    before = deepcopy(payload)
    assert extract_openai_tool_calls(payload) == expected
    assert payload == before


@pytest.mark.parametrize("headers", [False, True])
@pytest.mark.parametrize("damage", ["reordered", "empty-first", "empty-last"])
def test_section_recovery_preserves_raw_text_when_no_complete_ordered_block_exists(headers, damage):
    labels = ["### REQUIREMENT", "### CHANGELOG", "### ASSUMPTIONS", "### OPEN_QUESTIONS"] if headers else [
        "Requirement:", "Changelog:", "Assumptions:", "Open Questions:"]
    chunks = ["first", "second", "third", "fourth"]
    if damage == "reordered":
        labels[0], labels[1] = labels[1], labels[0]
    elif damage == "empty-first":
        chunks[0] = ""
    else:
        chunks[-1] = ""
    content = "\n".join(label + "\n" + chunk for label, chunk in zip(labels, chunks, strict=True)).strip()
    assert extract_openai_content(_payload(content="", reasoning_content=content)) == content


def test_section_recovery_keeps_latest_complete_auditor_block_and_trims_only_meta_tail():
    content = ("Critique: discarded\nCritique: retained\nPatches: precise\n"
               "Edge Cases: empty input\nTest Gaps: add refusal\nFinal polish: should not appear")
    assert extract_openai_content(_payload(content="", reasoning_content=content)) == (
        "### CRITIQUE\nretained\n\n### PATCHES\nprecise\n\n### EDGE_CASES\nempty input\n\n### TEST_GAPS\nadd refusal")
    assert recover_structured_reasoning_answer(" \r\n ") == ""


@pytest.mark.parametrize("raw,expected", [("fixture.invalid:8080", "http://fixture.invalid:8080/v1"),
    ("", "http://fallback.invalid/v1"), (" http://fixture.invalid/custom/ ", "http://fixture.invalid/custom")])
def test_base_url_normalization_preserves_explicit_path(raw, expected):
    assert normalize_openai_base_url(raw, default="http://fallback.invalid") == expected


def test_missing_host_and_nonobject_messages_have_explicit_admission_diagnostics():
    with pytest.raises(ValueError, match="Invalid OpenAI-compatible base URL"):
        normalize_openai_base_url("http:///missing", default="http://fallback.invalid")
    messages = [None, {"role": " SYSTEM "}, {}, {"role": "developer"}]
    assert validate_openai_messages(messages) == ["0:<non-object>", "2:<missing>", "3:developer"]
    assert messages[1]["role"] == " SYSTEM "


@pytest.mark.parametrize("usage,expected", [
    ({"prompt_tokens": 2.0, "completion_tokens": "3"}, (2, 3, 5)),
    ({"prompt_tokens": 1.5, "completion_tokens": []}, (None, None, None)),
    ({"prompt_tokens": "unknown", "completion_tokens": 3, "total_tokens": 8}, (None, 3, 8)),
    ([], (None, None, None)),
])
def test_usage_conversion_does_not_fabricate_missing_counts(usage, expected):
    assert extract_openai_usage({"usage": usage}) == expected


@pytest.mark.parametrize("bad", ["invalid", "-1", "nan", "inf", [], True])
def test_invalid_phase_durations_use_only_reported_backend_fallback(bad):
    payload = {"timings": {"prompt_ms": bad, "predicted_ms": bad, "total_ms": bad,
                          "prompt_eval_duration": 2_000_000, "eval_duration": 3_000_000, "total_duration": 7_000_000}}
    assert extract_openai_timings(payload, latency_ms=999) == (2.0, 3.0, 7.0)
    payload["timings"] = {"prompt_ms": bad, "predicted_ms": bad, "total_ms": bad}
    assert extract_openai_timings(payload, latency_ms=999) == (None, None, None)


def test_phase_duration_precedence_and_zero_remain_exact():
    payload = {"timings": {"prompt_ms": "0", "predicted_ms": "1.5", "total_ms": "4",
                          "prompt_eval_duration": 100_000_000},
               "prompt_eval_duration": 9_000_000, "eval_duration": 8_000_000, "total_duration": 20_000_000}
    assert extract_openai_timings(payload, latency_ms=500) == (0.0, 1.5, 4.0)
    payload.pop("timings")
    assert extract_openai_timings(payload, latency_ms=500) == (9.0, 8.0, 20.0)
