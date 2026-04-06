from __future__ import annotations

import pytest

from scripts.acceptance.check_monolith_readiness_gate import (
    _missing_required_combinations,
    _resolve_thresholds,
    aggregate_invalid_payload_signals,
    aggregate_metrics,
)
from scripts.acceptance.run_monolith_variant_matrix import build_combos, choose_default_variant, summarize_report


def test_build_combos_cartesian_product():
    combos = build_combos(["coder", "architect"], ["backend_only", "api_vue"])
    assert len(combos) == 4
    assert combos[0].builder_variant == "coder"
    assert combos[0].project_surface_profile == "backend_only"


def test_summarize_report_extracts_rates():
    report = {
        "run_count": 4,
        "completion_by_model": {
            "m1": {"passed": 2, "failed": 0},
            "m2": {"passed": 1, "failed": 1},
        },
        "pattern_counters": {
            "runtime_verifier_failures": 1,
            "guard_retry_scheduled": 2,
        },
    }
    summary = summarize_report(report)
    assert summary["run_count"] == 4
    assert summary["passed"] == 3
    assert summary["failed"] == 1
    assert summary["pass_rate"] == 0.75
    assert summary["runtime_failure_rate"] == 0.25
    assert summary["reviewer_rejection_rate"] == 0.5
    assert summary["invalid_payload_signals"] is None


# Layer: contract
@pytest.mark.contract
def test_summarize_report_preserves_invalid_payload_signals():
    report = {
        "run_count": 2,
        "completion_by_model": {"m1": {"passed": 1, "failed": 1}},
        "pattern_counters": {},
        "invalid_payload_signals": {"metrics_json": 1, "db_summary_json": 0},
    }
    summary = summarize_report(report)
    assert summary["invalid_payload_signals"] == {"db_summary_json": 0, "metrics_json": 1}


def test_choose_default_variant_prefers_higher_pass_rate():
    entries = [
        {
            "executed": True,
            "builder_variant": "coder",
            "summary": {
                "pass_rate": 0.80,
                "runtime_failure_rate": 0.20,
                "reviewer_rejection_rate": 0.30,
            },
        },
        {
            "executed": True,
            "builder_variant": "architect",
            "summary": {
                "pass_rate": 0.90,
                "runtime_failure_rate": 0.10,
                "reviewer_rejection_rate": 0.20,
            },
        },
    ]
    assert choose_default_variant(entries) == "architect"


def test_aggregate_metrics_average_values():
    entries = [
        {"executed": True, "summary": {"pass_rate": 0.8, "runtime_failure_rate": 0.2, "reviewer_rejection_rate": 0.4}},
        {"executed": True, "summary": {"pass_rate": 0.6, "runtime_failure_rate": 0.1, "reviewer_rejection_rate": 0.2}},
    ]
    metrics = aggregate_metrics(entries)
    assert metrics["pass_rate"] == pytest.approx(0.7)
    assert metrics["runtime_failure_rate"] == pytest.approx(0.15)
    assert metrics["reviewer_rejection_rate"] == pytest.approx(0.3)


def test_aggregate_metrics_preserves_zero_values():
    entries = [
        {"executed": True, "summary": {"pass_rate": 0.5, "runtime_failure_rate": 0.0, "reviewer_rejection_rate": 0.0}},
        {"executed": True, "summary": {"pass_rate": 0.5, "runtime_failure_rate": 0.0, "reviewer_rejection_rate": 0.0}},
    ]
    metrics = aggregate_metrics(entries)
    assert metrics["pass_rate"] == pytest.approx(0.5)
    assert metrics["runtime_failure_rate"] == pytest.approx(0.0)
    assert metrics["reviewer_rejection_rate"] == pytest.approx(0.0)


# Layer: contract
@pytest.mark.contract
def test_aggregate_invalid_payload_signals_sums_counts():
    entries = [
        {
            "builder_variant": "coder",
            "project_surface_profile": "backend_only",
            "summary": {"invalid_payload_signals": {"metrics_json": 1, "db_summary_json": 0}},
        },
        {
            "builder_variant": "architect",
            "project_surface_profile": "api_vue",
            "summary": {"invalid_payload_signals": {"metrics_json": 0, "db_summary_json": 2}},
        },
    ]
    signals, failures = aggregate_invalid_payload_signals(entries)
    assert failures == []
    assert signals == {"db_summary_json": 2, "metrics_json": 1}


# Layer: contract
@pytest.mark.contract
def test_aggregate_invalid_payload_signals_rejects_missing_or_malformed_values():
    entries = [
        {
            "builder_variant": "coder",
            "project_surface_profile": "backend_only",
            "summary": {},
        },
        {
            "builder_variant": "architect",
            "project_surface_profile": "api_vue",
            "summary": {"invalid_payload_signals": {"metrics_json": -1}},
        },
    ]
    signals, failures = aggregate_invalid_payload_signals(entries)
    assert signals == {}
    assert failures == [
        "invalid_payload_signals missing or invalid for coder/backend_only",
        "invalid_payload_signals missing or invalid for architect/api_vue",
    ]


def test_missing_required_combinations_detected():
    entries = [{"builder_variant": "coder", "project_surface_profile": "backend_only"}]
    policy = {
        "required_combinations": [
            {"builder_variant": "coder", "project_surface_profile": "backend_only"},
            {"builder_variant": "architect", "project_surface_profile": "api_vue"},
        ]
    }
    missing = _missing_required_combinations(entries, policy)
    assert ("architect", "api_vue") in missing


def test_policy_thresholds_override_args():
    class _Args:
        min_pass_rate = 0.1
        max_runtime_failure_rate = 0.9
        max_reviewer_rejection_rate = 0.9
        min_executed_entries = 1

    thresholds = _resolve_thresholds(
        _Args(),
        {
            "thresholds": {
                "min_pass_rate": 0.8,
                "max_runtime_failure_rate": 0.3,
                "max_reviewer_rejection_rate": 0.4,
                "max_invalid_payload_signals": 0,
                "min_executed_entries": 2,
            }
        },
    )
    assert thresholds["min_pass_rate"] == 0.8
    assert thresholds["max_runtime_failure_rate"] == 0.3
    assert thresholds["max_reviewer_rejection_rate"] == 0.4
    assert thresholds["max_invalid_payload_signals"] == 0
    assert thresholds["min_executed_entries"] == 2
