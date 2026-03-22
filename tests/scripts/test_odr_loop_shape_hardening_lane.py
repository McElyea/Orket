from pathlib import Path

from scripts.odr.model_role_fit_compare import build_pair_compare_payload
from scripts.odr.model_role_fit_lane import build_lane_bootstrap_payload, load_lane_config, load_matrix_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ODRLoopShapeHardening"
    / "LSH03222026"
    / "odr_loop_shape_hardening_lane_config.json"
)


def test_load_loop_shape_hardening_lane_freezes_fixed_pair_and_policy() -> None:
    """Layer: contract. Verifies the loop-shape lane freezes one fixed pair, one scenario family, and one prompt-hardening policy."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)

    assert config["locked_budgets"] == [5, 9]
    assert config["scenario_set"]["scenario_ids"] == ["missing_constraint_resolved", "overfitting"]
    assert registry["preferred_triples"] == []
    assert [pair.pair_id for pair in registry["primary_pairs"]] == ["command_r_35b__gemma3_27b"]
    assert config["protocol_hardening"]["architect_extra_rules"]
    assert config["protocol_hardening"]["auditor_extra_rules"]


def test_loop_shape_bootstrap_and_compare_snapshot_protocol_hardening() -> None:
    """Layer: contract. Verifies the fixed-pair lane emits the hardening policy in bootstrap and compare snapshots so the protocol variant is auditable."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)

    bootstrap = build_lane_bootstrap_payload(
        config,
        registry,
        inventory_rows=[
            {"model_id": "Command-R:35B", "provider": "ollama", "status": "ok"},
            {"model_id": "gemma3:27b", "provider": "ollama", "status": "ok"},
        ],
    )
    compare = build_pair_compare_payload(
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
            }
        ],
    )

    assert bootstrap["lane_config_snapshot"]["protocol_hardening"] == config["protocol_hardening"]
    assert compare["lane_config_snapshot"]["protocol_hardening"] == config["protocol_hardening"]
