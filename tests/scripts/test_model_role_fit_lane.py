import json
from pathlib import Path

from scripts.odr.model_role_fit_lane import (
    build_lane_bootstrap_payload,
    load_lane_config,
    load_matrix_registry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LANE_CONFIG_PATH = (
    REPO_ROOT / "docs" / "projects" / "archive" / "ODRModelRoleFit" / "MRF03212026" / "odr_model_role_fit_lane_config.json"
)


def test_load_model_role_fit_lane_config_and_registry_are_frozen() -> None:
    """Layer: contract. Verifies the model-role fit lane config and registry freeze the accepted serial pair-selection authority."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)

    assert config["continuity_mode"] == "v1_compiled_shared_state"
    assert config["locked_budgets"] == [5, 9]
    assert config["scenario_set"]["scenario_ids"] == ["missing_constraint_resolved", "overfitting"]
    assert config["structural_disqualification"] == {
        "stop_reasons": ["CODE_LEAK", "FORMAT_VIOLATION"],
        "max_failure_rate": 0.5,
    }
    assert config["role_timeout_sec"] == 300
    assert [pair.pair_id for pair in registry["primary_pairs"][:3]] == [
        "magistral_small_2509__gemma3_27b",
        "gemma3_27b__magistral_small_2509",
        "llama_3_3_70b_instruct__gemma3_27b",
    ]
    assert [triple.triple_id for triple in registry["preferred_triples"]] == [
        "llama_3_3_70b_instruct__gemma3_27b__magistral_small_2509",
        "magistral_small_2509__gemma3_27b__llama_3_3_70b_instruct",
        "gemma3_27b__llama_3_3_70b_instruct__magistral_small_2509",
    ]


def test_build_lane_bootstrap_payload_records_inventory_and_authority() -> None:
    """Layer: contract. Verifies the bootstrap payload snapshots the frozen lane authority and inventory preflight rows."""
    config = load_lane_config(LANE_CONFIG_PATH)
    registry = load_matrix_registry(config)

    payload = build_lane_bootstrap_payload(
        config,
        registry,
        inventory_rows=[
            {"model_id": "gemma3:27b", "provider": "ollama", "status": "ok"},
            {"model_id": "mistralai/magistral-small-2509", "provider": "lmstudio", "status": "ok"},
        ],
    )

    assert payload["schema_version"] == "odr.model_role_fit.bootstrap.v1"
    assert payload["lane_config_snapshot"]["config_path"] == str(LANE_CONFIG_PATH.resolve())
    assert payload["lane_config_snapshot"]["continuity_mode"] == "v1_compiled_shared_state"
    assert payload["matrix_registry_snapshot"]["path"] == str(Path(config["matrix_registry_path"]))
    assert payload["inventory_preflight"][0]["model_id"] == "gemma3:27b"
    assert json.loads(json.dumps(payload))["lane_config_snapshot"]["locked_budgets"] == [5, 9]
