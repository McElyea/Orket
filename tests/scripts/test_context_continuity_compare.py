import json
from pathlib import Path

import pytest

from scripts.odr.context_continuity_compare import build_context_continuity_compare_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_lane_config.json"
)
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "context_continuity" / "compare_input.json"


def test_build_context_continuity_compare_payload_applies_locked_v0_thresholds() -> None:
    """Layer: contract. Verifies the compare payload applies the locked V0 and V1 Section 15 thresholds at 5 and 9 rounds."""
    payload = build_context_continuity_compare_payload(FIXTURE_PATH, config_path=LANE_CONFIG_PATH)

    assert payload["schema_version"] == "odr.context_continuity.compare.v2"
    assert payload["lane_config_snapshot"]["decision_thresholds"]["v0"] == {
        "convergence_gain_min_percentage_points": 20.0,
        "absolute_converged_case_delta_min": 1,
        "max_active_context_size_ratio_vs_control": 2.0,
        "max_latency_ratio_vs_control": 2.5,
    }
    assert payload["lane_config_snapshot"]["decision_thresholds"]["v1"] == {
        "convergence_gain_min_percentage_points": 10.0,
        "absolute_converged_case_delta_min": 1,
        "carry_forward_integrity_gain_min_percentage_points": 15.0,
        "max_active_context_size_ratio_vs_v0": 1.5,
        "max_latency_ratio_vs_v0": 1.75,
    }
    assert len(payload["scenario_runs"]) == 12
    assert len(payload["pair_budget_aggregates"]) == 6
    assert len(payload["primary_budget_aggregates"]) == 6
    assert payload["scenario_runs"][0]["stop_reason"] == "MAX_ROUNDS"
    assert payload["scenario_runs"][0]["rounds_consumed"] == 5

    aggregates = {
        (int(row["locked_budget"]), str(row["continuity_mode"])): row
        for row in payload["pair_budget_aggregates"]
    }
    assert aggregates[(5, "control_current_replay")]["convergence_rate"] == pytest.approx(0.0)
    assert aggregates[(5, "v0_log_derived_replay")]["convergence_rate"] == pytest.approx(0.5)
    assert aggregates[(5, "v1_compiled_shared_state")]["convergence_rate"] == pytest.approx(0.5)
    assert aggregates[(9, "control_current_replay")]["convergence_rate"] == pytest.approx(1.0)
    assert aggregates[(9, "v0_log_derived_replay")]["convergence_rate"] == pytest.approx(1.0)
    assert aggregates[(9, "v1_compiled_shared_state")]["convergence_rate"] == pytest.approx(0.5)
    assert aggregates[(5, "control_current_replay")]["median_round_active_context_size_bytes"] == pytest.approx(770.0)
    assert aggregates[(5, "v0_log_derived_replay")]["median_round_active_context_size_bytes"] == pytest.approx(1380.0)
    assert aggregates[(5, "v1_compiled_shared_state")]["median_round_active_context_size_bytes"] == pytest.approx(1695.0)

    verdicts = {
        (str(row["continuity_mode"]), int(row["locked_budget"])): row for row in payload["budget_verdicts"]
    }
    budget5 = verdicts[("v0_log_derived_replay", 5)]
    assert budget5["verdict"] == "worthwhile_at_5_rounds"
    assert budget5["absolute_converged_case_delta"] == 1
    assert budget5["percentage_point_convergence_delta"] == pytest.approx(50.0)
    assert budget5["threshold_inputs"]["scenario_run_count"] == 2
    assert budget5["threshold_inputs"]["actual_active_context_size_ratio_vs_control"] == pytest.approx(1380.0 / 770.0)
    assert budget5["threshold_inputs"]["actual_latency_ratio_vs_control"] == pytest.approx(135.0 / 100.0)
    assert budget5["disqualifying_regressions"] == []

    budget9 = verdicts[("v0_log_derived_replay", 9)]
    assert budget9["verdict"] == "not_materially_worthwhile"
    assert budget9["absolute_converged_case_delta"] == 0
    assert budget9["percentage_point_convergence_delta"] == pytest.approx(0.0)
    assert budget9["threshold_inputs"]["scenario_run_count"] == 2
    assert budget9["disqualifying_regressions"] == [
        "convergence_gain_below_threshold",
        "absolute_converged_case_delta_below_threshold",
    ]

    v1_budget5 = verdicts[("v1_compiled_shared_state", 5)]
    assert v1_budget5["verdict"] == "continuity_quality_success_only"
    assert v1_budget5["absolute_converged_case_delta"] == 0
    assert v1_budget5["percentage_point_convergence_delta"] == pytest.approx(0.0)
    assert v1_budget5["threshold_inputs"]["percentage_point_carry_forward_integrity_delta"] == pytest.approx(20.0)
    assert v1_budget5["disqualifying_regressions"] == [
        "convergence_gain_below_threshold",
        "absolute_converged_case_delta_below_threshold",
    ]

    v1_budget9 = verdicts[("v1_compiled_shared_state", 9)]
    assert v1_budget9["verdict"] == "not_materially_worthwhile"
    assert v1_budget9["absolute_converged_case_delta"] == -1
    assert v1_budget9["percentage_point_convergence_delta"] == pytest.approx(-50.0)
    assert v1_budget9["disqualifying_regressions"] == [
        "carry_forward_integrity_gain_below_threshold",
        "convergence_regressed",
        "absolute_converged_case_delta_negative",
        "reopened_decision_rate_increase",
        "contradiction_rate_increase",
    ]
