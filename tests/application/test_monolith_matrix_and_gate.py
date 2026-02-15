from __future__ import annotations

import pytest

from scripts.run_monolith_variant_matrix import build_combos, choose_default_variant, summarize_report
from scripts.check_monolith_readiness_gate import aggregate_metrics


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
