from __future__ import annotations

from scripts.acceptance.check_microservices_pilot_stability import evaluate_pilot_stability


def _artifact(
    pass_delta: float,
    runtime_delta: float,
    reviewer_delta: float,
    *,
    invalid_signals: dict | None = None,
    invalid_totals: dict | None = None,
    invalid_failures: list[str] | None = None,
) -> dict:
    return {
        "comparison": {
            "available": True,
            "pass_rate_delta_microservices_minus_monolith": pass_delta,
            "runtime_failure_rate_delta_microservices_minus_monolith": runtime_delta,
            "reviewer_rejection_rate_delta_microservices_minus_monolith": reviewer_delta,
            "invalid_payload_signals_by_architecture": invalid_signals
            if invalid_signals is not None
            else {
                "force_monolith": {"db_summary_json": 0, "metrics_json": 0},
                "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
            },
            "invalid_payload_signal_totals_by_architecture": invalid_totals
            if invalid_totals is not None
            else {"force_monolith": 0, "force_microservices": 0},
            "invalid_payload_failures": invalid_failures if invalid_failures is not None else [],
        }
    }


# Layer: contract
def test_stability_passes_with_two_consecutive_stable_artifacts() -> None:
    result = evaluate_pilot_stability(
        [
            _artifact(0.0, 0.0, 0.0),
            _artifact(0.1, 0.0, -0.1),
        ],
        required_consecutive=2,
    )
    assert result["stable"] is True
    assert result["failures"] == []


# Layer: contract
def test_stability_fails_when_tail_artifact_regresses_pass_rate() -> None:
    result = evaluate_pilot_stability(
        [
            _artifact(0.2, 0.0, 0.0),
            _artifact(-0.1, 0.0, 0.0),
        ],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert any("pass_rate_delta" in item for item in result["failures"])


# Layer: contract
def test_stability_fails_when_insufficient_artifacts() -> None:
    result = evaluate_pilot_stability(
        [_artifact(0.0, 0.0, 0.0)],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert "insufficient artifacts" in result["failures"][0]


# Layer: contract
def test_stability_fails_when_invalid_payload_totals_are_non_zero() -> None:
    result = evaluate_pilot_stability(
        [
            _artifact(
                0.0,
                0.0,
                0.0,
                invalid_signals={
                    "force_monolith": {"db_summary_json": 1, "metrics_json": 0},
                    "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
                },
                invalid_totals={"force_monolith": 1, "force_microservices": 0},
            ),
            _artifact(0.0, 0.0, 0.0),
        ],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert any("invalid_payload_signals[force_monolith]" in item for item in result["failures"])


# Layer: contract
def test_stability_fails_when_invalid_payload_detail_is_missing() -> None:
    result = evaluate_pilot_stability(
        [
            {
                "comparison": {
                    "available": True,
                    "pass_rate_delta_microservices_minus_monolith": 0.0,
                    "runtime_failure_rate_delta_microservices_minus_monolith": 0.0,
                    "reviewer_rejection_rate_delta_microservices_minus_monolith": 0.0,
                }
            },
            _artifact(0.0, 0.0, 0.0),
        ],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert any("comparison missing or invalid" in item for item in result["failures"])


# Layer: contract
def test_stability_fails_when_invalid_payload_totals_drift_from_detail() -> None:
    result = evaluate_pilot_stability(
        [
            _artifact(
                0.0,
                0.0,
                0.0,
                invalid_signals={
                    "force_monolith": {"db_summary_json": 1, "metrics_json": 0},
                    "force_microservices": {"db_summary_json": 0, "metrics_json": 0},
                },
                invalid_totals={"force_monolith": 0, "force_microservices": 0},
            ),
            _artifact(0.0, 0.0, 0.0),
        ],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert any("comparison missing or invalid" in item for item in result["failures"])
