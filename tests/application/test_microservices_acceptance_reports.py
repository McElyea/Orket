from __future__ import annotations

from orket.application.services.microservices_acceptance_reports import (
    normalize_architecture_pilot_comparison,
    normalize_live_acceptance_pattern_report,
    normalize_microservices_pilot_stability_report,
    normalize_microservices_unlock_report,
)


def _valid_unlock_criteria() -> dict[str, dict[str, object]]:
    return {
        "monolith_readiness_gate": {"ok": True, "failures": []},
        "matrix_stability": {"ok": True, "failures": []},
        "governance_stability": {"ok": True, "failures": []},
    }


# Layer: contract
def test_normalize_microservices_unlock_report_accepts_valid_payload() -> None:
    payload = {
        "unlocked": True,
        "criteria": _valid_unlock_criteria(),
        "failures": [],
        "recommended_default_builder_variant": "coder",
    }

    normalized = normalize_microservices_unlock_report(payload)

    assert normalized["unlocked"] is True
    assert normalized["criteria"]["matrix_stability"]["ok"] is True
    assert normalized["recommended_default_builder_variant"] == "coder"


# Layer: contract
def test_normalize_microservices_unlock_report_rejects_internally_inconsistent_payload() -> None:
    payload = {
        "unlocked": False,
        "criteria": _valid_unlock_criteria(),
        "failures": ["matrix_stability: pass_rate below threshold"],
    }

    assert normalize_microservices_unlock_report(payload) == {}


# Layer: contract
def test_normalize_architecture_pilot_comparison_accepts_valid_payload() -> None:
    payload = {
        "available": True,
        "pass_rate_delta_microservices_minus_monolith": 0.1,
        "runtime_failure_rate_delta_microservices_minus_monolith": 0.0,
        "reviewer_rejection_rate_delta_microservices_minus_monolith": -0.1,
        "invalid_payload_signals_by_architecture": {
            "force_monolith": {"db_summary_json": 0, "metrics_json": 0},
            "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
        },
        "invalid_payload_signal_totals_by_architecture": {
            "force_monolith": 0,
            "force_microservices": 0,
        },
        "invalid_payload_failures": [],
    }

    normalized = normalize_architecture_pilot_comparison(payload)

    assert normalized is not None
    assert normalized["available"] is True
    assert normalized["invalid_payload_signal_totals_by_architecture"]["force_monolith"] == 0


# Layer: contract
def test_normalize_architecture_pilot_comparison_rejects_mismatched_invalid_payload_totals() -> None:
    payload = {
        "available": True,
        "pass_rate_delta_microservices_minus_monolith": 0.0,
        "runtime_failure_rate_delta_microservices_minus_monolith": 0.0,
        "reviewer_rejection_rate_delta_microservices_minus_monolith": 0.0,
        "invalid_payload_signals_by_architecture": {
            "force_monolith": {"db_summary_json": 1, "metrics_json": 0},
            "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
        },
        "invalid_payload_signal_totals_by_architecture": {
            "force_monolith": 0,
            "force_microservices": 0,
        },
        "invalid_payload_failures": [],
    }

    assert normalize_architecture_pilot_comparison(payload) is None


# Layer: contract
def test_normalize_live_acceptance_pattern_report_accepts_valid_payload() -> None:
    payload = {
        "batch_id": "batch-1",
        "run_count": 2,
        "session_status_counts": {"done": 1, "terminal_failure": 1},
        "pattern_counters": {"done_chain_mismatch": 0, "guard_retry_scheduled": 1},
        "invalid_payload_signals": {"db_summary_json": 0, "metrics_json": 0},
    }

    normalized = normalize_live_acceptance_pattern_report(payload)

    assert normalized["batch_id"] == "batch-1"
    assert normalized["run_count"] == 2
    assert normalized["session_status_counts"]["terminal_failure"] == 1


# Layer: contract
def test_normalize_live_acceptance_pattern_report_rejects_inconsistent_status_counts() -> None:
    payload = {
        "run_count": 2,
        "session_status_counts": {"done": 1},
        "pattern_counters": {"done_chain_mismatch": 0, "guard_retry_scheduled": 0},
        "invalid_payload_signals": {"db_summary_json": 0, "metrics_json": 0},
    }

    assert normalize_live_acceptance_pattern_report(payload) == {}


# Layer: contract
def test_normalize_microservices_pilot_stability_report_accepts_valid_payload() -> None:
    payload = {
        "stable": True,
        "required_consecutive": 2,
        "artifact_count": 2,
        "checks": [
            {"stable": True, "failures": []},
            {"stable": True, "failures": []},
        ],
        "failures": [],
    }

    normalized = normalize_microservices_pilot_stability_report(payload)

    assert normalized["stable"] is True
    assert normalized["artifact_count"] == 2
    assert len(normalized["checks"]) == 2


# Layer: contract
def test_normalize_microservices_pilot_stability_report_rejects_inconsistent_payload() -> None:
    payload = {
        "stable": True,
        "required_consecutive": 2,
        "artifact_count": 1,
        "checks": [
            {"stable": True, "failures": []},
            {"stable": False, "failures": ["unexpected tail failure"]},
        ],
        "failures": ["unexpected top-level failure"],
    }

    assert normalize_microservices_pilot_stability_report(payload) == {}
