from __future__ import annotations

import pytest

from scripts.odr.run_odr_7b_baseline import _interpret_7b_results

pytestmark = pytest.mark.unit


def test_interpret_7b_results_reports_semantic_non_convergence_when_unresolved_decisions_dominate() -> None:
    rows = [
        {
            "architect_model": "qwen2.5-coder:7b",
            "auditor_model": "qwen2.5:7b",
            "convergence_rate": 0.0,
            "code_leak_rate": 0.0,
            "format_violation_rate": 0.0,
            "mean_rounds_to_stop": 5.0,
            "stop_reason_distribution": {"UNRESOLVED_DECISIONS": 3},
        }
    ]

    result = _interpret_7b_results(rows)

    assert result["verdict"] == "FAIL_NO_CONVERGENCE"
    assert result["failure_mode"] == "semantic_non_convergence_unresolved_decisions"
    assert result["dominant_stop_reason"] == "UNRESOLVED_DECISIONS"
    assert any("semantic non-convergence" in note for note in result["notes"])
    assert all("FORMAT_VIOLATION" not in note for note in result["notes"])


def test_interpret_7b_results_reports_format_instability_when_format_violations_dominate() -> None:
    rows = [
        {
            "architect_model": "qwen2.5-coder:7b",
            "auditor_model": "qwen2.5:7b",
            "convergence_rate": 0.0,
            "code_leak_rate": 0.0,
            "format_violation_rate": 1.0,
            "mean_rounds_to_stop": 2.0,
            "stop_reason_distribution": {"FORMAT_VIOLATION": 3},
        }
    ]

    result = _interpret_7b_results(rows)

    assert result["verdict"] == "FAIL_NO_CONVERGENCE"
    assert result["failure_mode"] == "format_instability"
    assert result["dominant_stop_reason"] == "FORMAT_VIOLATION"
    assert any("format instability" in note for note in result["notes"])
    assert any("FORMAT_VIOLATION" in note for note in result["notes"])
