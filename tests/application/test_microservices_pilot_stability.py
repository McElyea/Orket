from __future__ import annotations

from scripts.check_microservices_pilot_stability import evaluate_pilot_stability


def _artifact(pass_delta: float, runtime_delta: float, reviewer_delta: float) -> dict:
    return {
        "comparison": {
            "available": True,
            "pass_rate_delta_microservices_minus_monolith": pass_delta,
            "runtime_failure_rate_delta_microservices_minus_monolith": runtime_delta,
            "reviewer_rejection_rate_delta_microservices_minus_monolith": reviewer_delta,
        }
    }


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


def test_stability_fails_when_insufficient_artifacts() -> None:
    result = evaluate_pilot_stability(
        [_artifact(0.0, 0.0, 0.0)],
        required_consecutive=2,
    )
    assert result["stable"] is False
    assert "insufficient artifacts" in result["failures"][0]
