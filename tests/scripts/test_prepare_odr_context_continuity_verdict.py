import json
from pathlib import Path

from scripts.odr.prepare_odr_context_continuity_compare import prepare_context_continuity_compare
from scripts.odr.prepare_odr_context_continuity_verdict import prepare_context_continuity_verdict

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
COMPARE_INPUT_PATH = REPO_ROOT / "tests" / "fixtures" / "context_continuity" / "compare_input.json"
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


def test_prepare_context_continuity_verdict_uses_configured_output_path(tmp_path: Path) -> None:
    """Layer: integration. Verifies the verdict harness writes diff-ledger output to the config-locked verdict path."""
    config = json.loads(LANE_CONFIG_PATH.read_text(encoding="utf-8"))
    config["pre_registration_record"] = str(REAL_PREREG_PATH)
    config["output_schema"] = str(REAL_SCHEMA_PATH)
    config["v0_replay_contract"] = str(REAL_V0_REPLAY_CONTRACT_PATH)
    config["v1_state_contract"] = str(REAL_V1_STATE_CONTRACT_PATH)
    compare_out = tmp_path / "compare.json"
    verdict_out = tmp_path / "verdict.json"
    config["artifact_paths"]["root"] = str(tmp_path / "artifacts")
    config["artifact_paths"]["bootstrap_summary"] = str(tmp_path / "bootstrap.json")
    config["artifact_paths"]["inspectability_output"] = str(tmp_path / "inspectability.json")
    config["artifact_paths"]["compare_output"] = str(compare_out)
    config["artifact_paths"]["verdict_output"] = str(verdict_out)
    config_path = tmp_path / "lane_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    prepare_context_continuity_compare(
        compare_input_path=COMPARE_INPUT_PATH,
        config_path=config_path,
    )
    persisted = prepare_context_continuity_verdict(config_path=config_path)

    assert len(persisted["budget_verdicts"]) == 4
    assert "diff_ledger" in persisted

    written = json.loads(verdict_out.read_text(encoding="utf-8"))
    assert written["source_compare_artifact"]["path"] == str(compare_out)
    assert written["summary"]["by_mode"]["v0_log_derived_replay"]["verdicts_by_budget"] == {
        "5": "worthwhile_at_5_rounds",
        "9": "not_materially_worthwhile",
    }
    assert written["summary"]["by_mode"]["v1_compiled_shared_state"]["verdicts_by_budget"] == {
        "5": "continuity_quality_success_only",
        "9": "not_materially_worthwhile",
    }
