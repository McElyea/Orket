"""Benchmark aggregates must cover every included turn with reported timing."""
from __future__ import annotations

import json

import pytest

from scripts.benchmarks.live_card_benchmark_runner import _extract_token_metrics_from_log


def _turn(prompt, predicted, *, legacy=False, tokens=2):
    values = {"prompt_tokens":tokens,"output_tokens":1,"total_tokens":3,
              "prompt_ms":prompt,"predicted_ms":predicted}
    if not legacy:
        values.update(timing_schema_version="model_provider_timing.v1",
                      timing_posture="reported" if prompt is not None and predicted is not None else "partial")
    return {"event":"turn_complete","data":{"session_id":"session-1","tokens":values}}


@pytest.mark.parametrize("rows", [
    [_turn(100,None),_turn(None,200)],
    [_turn(100,200),_turn(None,None)],
    [_turn(100,200,legacy=True)],
    [_turn(100,200),_turn(100,200,legacy=True)],
    [_turn(True,200)],
])
# Layer: integration
def test_benchmark_refuses_incomplete_or_unverified_timing_totals(tmp_path, rows):
    path = tmp_path/"events.log"
    path.write_text("\n".join(json.dumps(row) for row in rows),encoding="utf-8")
    metrics = _extract_token_metrics_from_log(log_path=path,session_id="session-1",total_turn_seconds=5)
    assert metrics["status"] == "TIMING_UNAVAILABLE"
    assert metrics["latencies"]["prefill_seconds"] is None
    assert metrics["latencies"]["decode_seconds"] is None
    assert metrics["throughput"]["generation_tokens_per_second"] is None


# Layer: integration
def test_benchmark_refuses_partial_token_totals_for_full_timing(tmp_path):
    path = tmp_path/"events.log"
    rows = [_turn(100,200),_turn(100,200,tokens=None)]
    path.write_text("\n".join(json.dumps(row) for row in rows),encoding="utf-8")
    metrics = _extract_token_metrics_from_log(log_path=path,session_id="session-1",total_turn_seconds=5)
    assert metrics["status"] == "TOKEN_COUNT_UNAVAILABLE"
    assert metrics["counts"]["prompt_tokens"] is None
    assert metrics["throughput"]["prompt_tokens_per_second"] is None


# Layer: integration
def test_benchmark_retains_complete_reported_zero_and_fractional_timings(tmp_path):
    path = tmp_path/"events.log"
    rows = [_turn(0,12.5),_turn(0,12.5)]
    path.write_text("\n".join(json.dumps(row) for row in rows),encoding="utf-8")
    metrics = _extract_token_metrics_from_log(log_path=path,session_id="session-1",total_turn_seconds=5)
    assert metrics["status"] == "OK"
    assert metrics["latencies"]["prefill_seconds"] == 0
    assert metrics["latencies"]["decode_seconds"] == 0.025
    assert metrics["throughput"]["generation_tokens_per_second"] == 80
