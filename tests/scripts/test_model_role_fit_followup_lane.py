# LIFECYCLE: live
from pathlib import Path

from scripts.odr.model_role_fit_compare import build_pair_compare_payload, build_pair_verdict_payload
from scripts.odr.model_role_fit_lane import load_lane_config, load_matrix_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ODRRoleFitFollowup"
    / "RFU03222026"
    / "odr_role_fit_followup_lane_config.json"
)


def test_load_model_role_fit_followup_lane_config_is_reviewer_anchored() -> None:
    """Layer: contract. Verifies the follow-up lane stays inside the narrowed three-architect bakeoff anchored on gemma3:27b as reviewer."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)

    assert config["locked_budgets"] == [5, 9]
    assert config["scenario_set"]["scenario_ids"] == ["missing_constraint_resolved", "overfitting"]
    assert [pair.pair_id for pair in registry["primary_pairs"]] == [
        "command_r_35b__gemma3_27b",
        "llama_3_3_70b_instruct__gemma3_27b",
        "magistral_small_2509__gemma3_27b",
    ]
    assert {pair.reviewer_model for pair in registry["primary_pairs"]} == {"gemma3:27b"}
    assert registry["preferred_triples"] == []


def test_followup_pair_verdict_marks_triple_phase_not_configured() -> None:
    """Layer: contract. Verifies the reviewer-anchored follow-up lane does not claim an admitted triple phase when no preferred triples are configured."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)
    pair_compare = build_pair_compare_payload(
        config=config,
        registry=registry,
        raw_rows=[
            {
                "entity_id": "command_r_35b__gemma3_27b",
                "scenario_id": "missing_constraint_resolved",
                "locked_budget": 5,
                "converged": False,
                "stop_reason": "UNRESOLVED_DECISIONS",
                "rounds_consumed": 5,
                "reopened_decision_count": 0,
                "contradiction_count": 0,
                "regression_count": 0,
                "carry_forward_integrity": 1.0,
                "round_latency_ms": [100],
                "round_active_context_size_bytes": [1000],
                "round_active_context_size_tokens": [256],
            },
            {
                "entity_id": "magistral_small_2509__gemma3_27b",
                "scenario_id": "missing_constraint_resolved",
                "locked_budget": 5,
                "converged": False,
                "stop_reason": "UNRESOLVED_DECISIONS",
                "rounds_consumed": 5,
                "reopened_decision_count": 0,
                "contradiction_count": 0,
                "regression_count": 0,
                "carry_forward_integrity": 1.0,
                "round_latency_ms": [101],
                "round_active_context_size_bytes": [1001],
                "round_active_context_size_tokens": [257],
            },
        ],
    )
    pair_verdict = build_pair_verdict_payload(
        config=config,
        registry=registry,
        pair_compare_payload=pair_compare,
    )

    assert pair_verdict["selected_pairs_for_triples"] == [
        "command_r_35b__gemma3_27b",
        "magistral_small_2509__gemma3_27b",
    ]
    assert pair_verdict["triple_phase_status"] == "not_configured"
    assert pair_verdict["triple_phase_skip_reason"] == "no_preferred_triples_configured"
