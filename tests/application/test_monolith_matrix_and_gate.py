from __future__ import annotations

import pytest

from scripts.run_monolith_variant_matrix import build_combos, choose_default_variant, summarize_report
from scripts.check_monolith_readiness_gate import aggregate_metrics, _missing_required_combinations, _resolve_thresholds


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
                "min_executed_entries": 2,
            }
        },
    )
    assert thresholds["min_pass_rate"] == 0.8
    assert thresholds["max_runtime_failure_rate"] == 0.3
    assert thresholds["max_reviewer_rejection_rate"] == 0.4
    assert thresholds["min_executed_entries"] == 2
