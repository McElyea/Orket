# LIFECYCLE: live
from pathlib import Path

from scripts.odr.round_cap_probe import _movement_analysis, load_probe_config, load_probe_registry

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ODRRoundCapProbe"
    / "RCP03222026"
    / "odr_round_cap_probe_lane_config.json"
)


def test_round_cap_probe_config_freezes_probe_budget_and_registry() -> None:
    """Layer: contract. Verifies the round-cap probe freezes a dedicated 20-round budget and only the prior MAX_ROUNDS cases."""
    config = load_probe_config(CONFIG_PATH)
    registry = load_probe_registry(config)

    assert config["probe_budget"] == 20
    assert config["continuity_mode"] == "v1_compiled_shared_state"
    assert [spec.probe_id for spec in registry["probe_runs"]] == [
        "command_r_35b__gemma3_27b__missing_constraint_resolved__20",
        "magistral_small_2509__gemma3_27b__missing_constraint_resolved__20",
        "magistral_small_2509__gemma3_27b__overfitting__20",
    ]


def test_movement_analysis_flags_flatline_before_round_cap() -> None:
    """Layer: unit. Verifies the probe can distinguish a true round-cap bind from a run that stopped changing earlier."""
    inspect_row = {
        "rounds": [
            {
                "source_inputs": [
                    {"artifact_kind": "current_canonical_artifact", "content": "A"},
                    {"artifact_kind": "latest_architect_delta", "content": "x1"},
                ]
            },
            {
                "source_inputs": [
                    {"artifact_kind": "current_canonical_artifact", "content": "B"},
                    {"artifact_kind": "latest_architect_delta", "content": "x2"},
                    {"artifact_kind": "latest_auditor_critique", "content": "y1"},
                ]
            },
            {
                "source_inputs": [
                    {"artifact_kind": "current_canonical_artifact", "content": "B"},
                    {"artifact_kind": "latest_architect_delta", "content": "x2"},
                    {"artifact_kind": "latest_auditor_critique", "content": "y1"},
                ]
            },
            {
                "source_inputs": [
                    {"artifact_kind": "current_canonical_artifact", "content": "B"},
                    {"artifact_kind": "latest_architect_delta", "content": "x2"},
                    {"artifact_kind": "latest_auditor_critique", "content": "y1"},
                ]
            },
        ]
    }
    compare_row = {"stop_reason": "MAX_ROUNDS"}

    result = _movement_analysis(inspect_row, compare_row, probe_budget=20)

    assert result["requirement_last_change_round"] == 2
    assert result["requirement_flatline_round"] == 2
    assert result["last_any_change_round"] == 2
    assert result["round_cap_assessment"] == "flatlined_before_cap"


def test_movement_analysis_flags_round_cap_bind_only_when_movement_survives_to_cap() -> None:
    """Layer: unit. Verifies the 20-round probe recommends a higher round cap only when the run still changes through the probe budget."""
    inspect_row = {
        "rounds": [
            {
                "source_inputs": [
                    {"artifact_kind": "current_canonical_artifact", "content": f"Requirement {index}"},
                    {"artifact_kind": "latest_architect_delta", "content": f"Architect {index}"},
                    {"artifact_kind": "latest_auditor_critique", "content": f"Auditor {index}"},
                ]
            }
            for index in range(1, 21)
        ]
    }
    compare_row = {"stop_reason": "MAX_ROUNDS"}

    result = _movement_analysis(inspect_row, compare_row, probe_budget=20)

    assert result["last_any_change_round"] == 20
    assert result["round_cap_assessment"] == "round_cap_still_binding"
