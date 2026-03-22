import json
from pathlib import Path

from scripts.odr.prepare_odr_context_continuity_lane import prepare_lane_bootstrap

REPO_ROOT = Path(__file__).resolve().parents[2]
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


def test_prepare_lane_bootstrap_uses_machine_readable_config(tmp_path: Path) -> None:
    """Layer: integration. Verifies the bootstrap harness reads budgets, pairs, scenarios, and output paths from config."""
    out_path = tmp_path / "custom_bootstrap.json"
    config = {
        "schema_version": "odr.context_continuity.lane_config.v1",
        "last_updated": "2026-03-21",
        "requirements_authority": "odr_context_continuity_requirements.md",
        "implementation_authority": "odr_context_continuity_implementation_plan.md",
        "pre_registration_record": str(REAL_PREREG_PATH),
        "output_schema": str(REAL_SCHEMA_PATH),
        "v0_replay_contract": str(REAL_V0_REPLAY_CONTRACT_PATH),
        "v1_state_contract": str(REAL_V1_STATE_CONTRACT_PATH),
        "continuity_modes": [
            "control_current_replay",
            "v0_log_derived_replay",
            "v1_compiled_shared_state",
        ],
        "locked_budgets": [7],
        "scenario_set": {"id": "custom_scope", "scenario_ids": ["alpha", "beta", "gamma"]},
        "pair_scope": "single_pair_bounded",
        "selected_primary_pairs": [
            {
                "pair_id": "custom_pair",
                "architect_model": "arch-x",
                "architect_provider": "lmstudio",
                "auditor_model": "audit-y",
                "auditor_provider": "ollama",
            }
        ],
        "secondary_sensitivity_pairs": [],
        "threshold_table_reference": {
            "path": "odr_context_continuity_requirements.md",
            "sections": ["13", "15"],
        },
        "artifact_paths": {
            "root": str(tmp_path / "artifacts"),
            "bootstrap_summary": str(out_path),
            "inspectability_output": str(tmp_path / "inspectability.json"),
            "compare_output": str(tmp_path / "compare.json"),
            "verdict_output": str(tmp_path / "verdict.json"),
        },
        "mode_state_inputs": {
            "control_current_replay": [],
            "v0_log_derived_replay": ["replay_block"],
            "v1_compiled_shared_state": ["shared_state_snapshot", "role_view"],
        },
        "control_freeze": {
            "mode_id": "control_current_replay",
            "description": "Frozen control",
            "disallowed_additions": ["compiled shared state"],
        },
    }
    config_path = tmp_path / "lane_config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    persisted = prepare_lane_bootstrap(config_path=config_path)

    assert persisted["execution_scope"]["locked_budgets"] == [7]
    assert persisted["execution_scope"]["scenario_ids"] == ["alpha", "beta", "gamma"]
    assert persisted["execution_scope"]["selected_primary_pairs"][0]["pair_id"] == "custom_pair"
    assert persisted["canonical_output_paths"]["bootstrap_summary"] == str(out_path)

    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["execution_scope"]["selected_primary_pairs"][0]["architect_model"] == "arch-x"
    assert "diff_ledger" in written
