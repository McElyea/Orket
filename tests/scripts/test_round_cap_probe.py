# LIFECYCLE: live
import json
from pathlib import Path

import pytest

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


# Layer: contract
def test_round_cap_probe_config_freezes_probe_budget_and_registry() -> None:
    """Layer: contract. Checks the archived selection, without claiming retained benchmark evidence exists."""
    config = load_probe_config(CONFIG_PATH)
    registry = json.loads(Path(config["probe_registry_path"]).read_text(encoding="utf-8"))

    assert config["probe_budget"] == 20
    assert config["continuity_mode"] == "v1_compiled_shared_state"
    assert [spec["probe_id"] for spec in registry["probe_runs"]] == [
        "command_r_35b__gemma3_27b__missing_constraint_resolved__20",
        "magistral_small_2509__gemma3_27b__missing_constraint_resolved__20",
        "magistral_small_2509__gemma3_27b__overfitting__20",
    ]
    assert {spec["source_stop_reason"] for spec in registry["probe_runs"]} == {"MAX_ROUNDS"}
    assert [spec["source_locked_budget"] for spec in registry["probe_runs"]] == [5, 9, 5]


@pytest.mark.integration
@pytest.mark.parametrize("missing", [None, "source_config", "source_compare_artifact"])
# Layer: integration
def test_probe_registry_requires_source_files(tmp_path: Path, missing: str | None) -> None:
    """Layer: integration. Real fixture files prove resolution and missing-input refusal, not benchmark replay."""
    config = load_probe_config(CONFIG_PATH)
    registry = json.loads(Path(config["probe_registry_path"]).read_text(encoding="utf-8"))
    for index, spec in enumerate(registry["probe_runs"]):
        for key in ("source_config", "source_compare_artifact"):
            relative = f"{index}-{key}.json"
            spec[key] = relative
            if key != missing:
                (tmp_path / relative).write_text('{"fixture_only": true}', encoding="utf-8")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    config["probe_registry_path"] = str(registry_path)
    if missing:
        message = "source config" if missing == "source_config" else "source compare artifact"
        with pytest.raises(FileNotFoundError, match=message):
            load_probe_registry(config)
    else:
        loaded = load_probe_registry(config)
        assert len(loaded["probe_runs"]) == 3
        for index, spec in enumerate(loaded["probe_runs"]):
            assert spec.source_config_path == tmp_path / f"{index}-source_config.json"
            assert spec.source_compare_artifact_path == tmp_path / f"{index}-source_compare_artifact.json"


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
