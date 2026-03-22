import json
from pathlib import Path

import pytest

from scripts.odr.context_continuity_lane import (
    build_continuity_mode_registry,
    build_pair_budget_aggregate,
    build_primary_budget_aggregate,
    load_lane_config,
)

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
V0_REPLAY_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v0_replay_contract.json"
)
V1_STATE_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v1_state_contract.json"
)


def test_build_pair_budget_aggregate_uses_scenario_run_units() -> None:
    """Layer: unit. Verifies pair-budget aggregation is computed directly from scenario-run rows."""
    aggregate = build_pair_budget_aggregate(
        [
            {
                "converged": True,
                "reopened_decision_count": 0,
                "contradiction_count": 1,
                "regression_count": 0,
                "carry_forward_integrity": 1.0,
                "median_round_latency_ms": 100,
                "median_round_active_context_size_bytes": 800,
                "median_round_active_context_size_tokens": 400,
            },
            {
                "converged": False,
                "reopened_decision_count": 2,
                "contradiction_count": 0,
                "regression_count": 1,
                "carry_forward_integrity": 0.5,
                "median_round_latency_ms": 300,
                "median_round_active_context_size_bytes": 1200,
                "median_round_active_context_size_tokens": 600,
            },
        ],
        pair_id="pair-a",
        locked_budget=5,
        continuity_mode="control_current_replay",
    )

    assert aggregate["scenario_run_count"] == 2
    assert aggregate["convergence_rate"] == pytest.approx(0.5)
    assert aggregate["reopened_decision_rate"] == pytest.approx(1.0)
    assert aggregate["contradiction_rate"] == pytest.approx(0.5)
    assert aggregate["regression_rate"] == pytest.approx(0.5)
    assert aggregate["carry_forward_integrity"] == pytest.approx(0.75)
    assert aggregate["median_round_latency_ms"] == pytest.approx(200.0)
    assert aggregate["median_round_active_context_size_bytes"] == pytest.approx(1000.0)
    assert aggregate["median_round_active_context_size_tokens"] == pytest.approx(500.0)


def test_build_primary_budget_aggregate_equally_weights_pairs() -> None:
    """Layer: unit. Verifies primary aggregation equally weights pair-budget rows rather than scenario counts."""
    aggregate = build_primary_budget_aggregate(
        [
            {
                "convergence_rate": 1.0,
                "reopened_decision_rate": 0.0,
                "contradiction_rate": 0.0,
                "regression_rate": 0.0,
                "carry_forward_integrity": 1.0,
                "median_round_latency_ms": 100.0,
                "median_round_active_context_size_bytes": 800.0,
                "median_round_active_context_size_tokens": 200.0,
                "scenario_run_count": 1,
            },
            {
                "convergence_rate": 0.0,
                "reopened_decision_rate": 2.0,
                "contradiction_rate": 1.0,
                "regression_rate": 1.0,
                "carry_forward_integrity": 0.2,
                "median_round_latency_ms": 500.0,
                "median_round_active_context_size_bytes": 1600.0,
                "median_round_active_context_size_tokens": 800.0,
                "scenario_run_count": 10,
            },
        ],
        locked_budget=9,
        continuity_mode="v0_log_derived_replay",
    )

    assert aggregate["pair_count"] == 2
    assert aggregate["convergence_rate"] == pytest.approx(0.5)
    assert aggregate["reopened_decision_rate"] == pytest.approx(1.0)
    assert aggregate["contradiction_rate"] == pytest.approx(0.5)
    assert aggregate["regression_rate"] == pytest.approx(0.5)
    assert aggregate["carry_forward_integrity"] == pytest.approx(0.6)
    assert aggregate["median_round_active_context_size_bytes"] == pytest.approx(1200.0)
    assert aggregate["median_round_active_context_size_tokens"] == pytest.approx(500.0)


def test_load_lane_config_keeps_control_mode_isolated() -> None:
    """Layer: contract. Verifies the committed lane config keeps control_current_replay free of V0/V1 state inputs."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = {row["mode"]: row for row in build_continuity_mode_registry(config)}

    assert config["locked_budgets"] == [5, 9]
    assert registry["control_current_replay"]["state_inputs_required"] == []
    assert registry["v0_log_derived_replay"]["state_inputs_required"] == ["replay_block"]
    assert registry["v1_compiled_shared_state"]["state_inputs_required"] == ["shared_state_snapshot", "role_view"]


def test_load_lane_config_rejects_control_state_dependency(tmp_path: Path) -> None:
    """Layer: contract. Verifies the control mode fails closed if config drift tries to bind it to V0/V1 state."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_pair_preregistration.json"
    )
    config["output_schema"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_output_schema.json"
    )
    config["v0_replay_contract"] = str(V0_REPLAY_CONTRACT_PATH)
    config["v1_state_contract"] = str(V1_STATE_CONTRACT_PATH)
    config["mode_state_inputs"]["control_current_replay"] = ["replay_block"]
    config_path = tmp_path / "lane_config_bad.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="control_current_replay"):
        load_lane_config(config_path)


def test_load_lane_config_rejects_missing_inspectability_output_path(tmp_path: Path) -> None:
    """Layer: contract. Verifies CC-IMP-01 fails closed if the canonical inspectability artifact path is not locked."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_pair_preregistration.json"
    )
    config["output_schema"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_output_schema.json"
    )
    config["v0_replay_contract"] = str(V0_REPLAY_CONTRACT_PATH)
    config["v1_state_contract"] = str(V1_STATE_CONTRACT_PATH)
    del config["artifact_paths"]["inspectability_output"]
    config_path = tmp_path / "lane_config_missing_inspectability.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="inspectability_output"):
        load_lane_config(config_path)


def test_load_lane_config_rejects_missing_v0_replay_contract(tmp_path: Path) -> None:
    """Layer: contract. Verifies CC-IMP-02 fails closed if the deterministic V0 replay contract is not locked."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_pair_preregistration.json"
    )
    config["output_schema"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_output_schema.json"
    )
    config["v1_state_contract"] = str(V1_STATE_CONTRACT_PATH)
    del config["v0_replay_contract"]
    config_path = tmp_path / "lane_config_missing_v0_contract.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="v0_replay_contract"):
        load_lane_config(config_path)


def test_load_lane_config_rejects_missing_v1_state_contract(tmp_path: Path) -> None:
    """Layer: contract. Verifies CC-IMP-03 fails closed if the deterministic V1 state contract is not locked."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_pair_preregistration.json"
    )
    config["output_schema"] = str(
        REPO_ROOT
        / "docs"
        / "projects"
        / "archive"
        / "ContextContinuity"
        / "CC03212026"
        / "odr_context_continuity_output_schema.json"
    )
    config["v0_replay_contract"] = str(V0_REPLAY_CONTRACT_PATH)
    del config["v1_state_contract"]
    config_path = tmp_path / "lane_config_missing_v1_contract.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="v1_state_contract"):
        load_lane_config(config_path)
