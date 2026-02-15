from __future__ import annotations

from scripts.check_microservices_unlock import (
    _check_governance_stability,
    _check_matrix_stability,
    evaluate_unlock,
)


def _unlock_policy() -> dict:
    return {
        "criteria": {
            "monolith_readiness_gate": {"required": True},
            "matrix_stability": {
                "required": True,
                "min_executed_entries": 2,
                "min_project_surface_profiles": 2,
                "min_pass_rate": 0.7,
                "max_runtime_failure_rate": 0.3,
                "max_reviewer_rejection_rate": 0.5,
            },
            "governance_stability": {
                "required": True,
                "min_runs": 2,
                "max_terminal_failure_rate": 0.5,
                "max_guard_retry_rate": 1.0,
                "max_done_chain_mismatch": 0,
            },
        }
    }


def test_check_matrix_stability_passes_with_coverage_and_rates() -> None:
    matrix = {
        "entries": [
            {
                "executed": True,
                "project_surface_profile": "backend_only",
                "summary": {"pass_rate": 0.8, "runtime_failure_rate": 0.2, "reviewer_rejection_rate": 0.3},
            },
            {
                "executed": True,
                "project_surface_profile": "api_vue",
                "summary": {"pass_rate": 0.9, "runtime_failure_rate": 0.1, "reviewer_rejection_rate": 0.2},
            },
        ]
    }
    result = _check_matrix_stability(matrix, _unlock_policy())
    assert result["ok"] is True
    assert result["executed_entries"] == 2
    assert result["profile_count"] == 2


def test_check_governance_stability_detects_done_chain_mismatch() -> None:
    report = {
        "run_count": 4,
        "session_status_counts": {"done": 3, "terminal_failure": 1},
        "pattern_counters": {
            "guard_retry_scheduled": 2,
            "done_chain_mismatch": 1,
        },
    }
    result = _check_governance_stability(report, _unlock_policy())
    assert result["ok"] is False
    assert any("done_chain_mismatch" in item for item in result["failures"])


def test_evaluate_unlock_requires_live_report_when_governance_required() -> None:
    matrix = {
        "recommended_default_builder_variant": "coder",
        "entries": [
            {
                "executed": True,
                "builder_variant": "coder",
                "project_surface_profile": "backend_only",
                "summary": {"pass_rate": 0.9, "runtime_failure_rate": 0.1, "reviewer_rejection_rate": 0.2},
            },
            {
                "executed": True,
                "builder_variant": "coder",
                "project_surface_profile": "api_vue",
                "summary": {"pass_rate": 0.9, "runtime_failure_rate": 0.1, "reviewer_rejection_rate": 0.2},
            },
        ],
    }
    readiness_policy = {
        "required_combinations": [
            {"builder_variant": "coder", "project_surface_profile": "backend_only"},
            {"builder_variant": "coder", "project_surface_profile": "api_vue"},
        ],
        "thresholds": {
            "min_pass_rate": 0.7,
            "max_runtime_failure_rate": 0.3,
            "max_reviewer_rejection_rate": 0.5,
            "min_executed_entries": 2,
        },
    }
    result = evaluate_unlock(matrix, readiness_policy, _unlock_policy(), {})
    assert result["unlocked"] is False
    assert any("live acceptance report missing" in item for item in result["failures"])
