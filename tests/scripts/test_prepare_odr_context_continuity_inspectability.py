# LIFECYCLE: live
import json
from pathlib import Path

from scripts.odr.prepare_odr_context_continuity_inspectability import prepare_lane_inspectability

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
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "context_continuity" / "inspectability_input.json"
REAL_PREREG_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_pair_preregistration.json"
)
REAL_SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_output_schema.json"
)
REAL_V0_REPLAY_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v0_replay_contract.json"
)
REAL_V1_STATE_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v1_state_contract.json"
)


def test_prepare_lane_inspectability_uses_configured_output_path(tmp_path: Path) -> None:
    """Layer: integration. Verifies the inspectability harness reads the locked output path from machine-readable config."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(REAL_PREREG_PATH)
    config["output_schema"] = str(REAL_SCHEMA_PATH)
    config["v0_replay_contract"] = str(REAL_V0_REPLAY_CONTRACT_PATH)
    config["v1_state_contract"] = str(REAL_V1_STATE_CONTRACT_PATH)
    configured_out = tmp_path / "inspectability.json"
    config["artifact_paths"]["root"] = str(tmp_path / "artifacts")
    config["artifact_paths"]["bootstrap_summary"] = str(tmp_path / "bootstrap.json")
    config["artifact_paths"]["inspectability_output"] = str(configured_out)
    config["artifact_paths"]["compare_output"] = str(tmp_path / "compare.json")
    config["artifact_paths"]["verdict_output"] = str(tmp_path / "verdict.json")
    config_path = tmp_path / "lane_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    persisted = prepare_lane_inspectability(
        inspectability_input_path=FIXTURE_PATH,
        config_path=config_path,
    )

    assert len(persisted["scenario_run_artifacts"]) == 3
    assert persisted["scenario_run_artifacts"][0]["locked_budget"] == 5
    assert "diff_ledger" in persisted

    written = json.loads(configured_out.read_text(encoding="utf-8"))
    assert written["artifact_locations"]["inspectability_output"] == str(configured_out)
    assert {row["continuity_mode"] for row in written["scenario_run_artifacts"]} == {
        "control_current_replay",
        "v0_log_derived_replay",
        "v1_compiled_shared_state",
    }
