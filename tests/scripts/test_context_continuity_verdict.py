import json
from pathlib import Path

import pytest

from scripts.common.rerun_diff_ledger import _payload_digest
from scripts.odr.context_continuity_compare import build_context_continuity_compare_payload
from scripts.odr.context_continuity_verdict import build_context_continuity_verdict_payload

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


def test_build_context_continuity_verdict_payload_preserves_locked_budget_decisions(tmp_path: Path) -> None:
    """Layer: contract. Verifies the verdict artifact is a config-validated projection of the compare budget decisions."""
    compare_payload = build_context_continuity_compare_payload(COMPARE_INPUT_PATH, config_path=LANE_CONFIG_PATH)
    compare_path = tmp_path / "compare.json"
    compare_path.write_text(json.dumps(compare_payload, indent=2), encoding="utf-8")

    verdict_payload = build_context_continuity_verdict_payload(compare_path, config_path=LANE_CONFIG_PATH)

    assert verdict_payload["schema_version"] == "odr.context_continuity.verdict.v2"
    assert verdict_payload["pair_scope"] == "single_pair_bounded"
    assert verdict_payload["evidence_scope"] == "single_pair_bounded"
    assert verdict_payload["continuity_modes"] == ["v0_log_derived_replay", "v1_compiled_shared_state"]
    assert verdict_payload["source_compare_artifact"]["artifact_sha256"] == _payload_digest(compare_payload)
    assert verdict_payload["summary"]["by_mode"]["v0_log_derived_replay"] == {
        "global_verdict": None,
        "worthwhile_budgets": [5],
        "continuity_quality_success_only_budgets": [],
        "non_worthwhile_budgets": [9],
        "verdicts_by_budget": {
            "5": "worthwhile_at_5_rounds",
            "9": "not_materially_worthwhile",
        },
    }
    assert verdict_payload["summary"]["by_mode"]["v1_compiled_shared_state"] == {
        "global_verdict": None,
        "worthwhile_budgets": [],
        "continuity_quality_success_only_budgets": [5],
        "non_worthwhile_budgets": [9],
        "verdicts_by_budget": {
            "5": "continuity_quality_success_only",
            "9": "not_materially_worthwhile",
        },
    }

    budget_verdicts = {
        (str(row["continuity_mode"]), int(row["locked_budget"])): row for row in verdict_payload["budget_verdicts"]
    }
    assert budget_verdicts[("v0_log_derived_replay", 5)]["absolute_converged_case_delta"] == 1
    assert budget_verdicts[("v0_log_derived_replay", 9)]["disqualifying_regressions"] == [
        "convergence_gain_below_threshold",
        "absolute_converged_case_delta_below_threshold",
    ]
    assert budget_verdicts[("v1_compiled_shared_state", 5)]["verdict"] == "continuity_quality_success_only"


def test_build_context_continuity_verdict_payload_rejects_threshold_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies the verdict builder fails closed if compare evidence drifts away from locked thresholds."""
    compare_payload = build_context_continuity_compare_payload(COMPARE_INPUT_PATH, config_path=LANE_CONFIG_PATH)
    compare_payload["lane_config_snapshot"]["decision_thresholds"]["v0"]["convergence_gain_min_percentage_points"] = 25.0
    compare_path = tmp_path / "compare_drifted.json"
    compare_path.write_text(json.dumps(compare_payload, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="decision thresholds do not match"):
        build_context_continuity_verdict_payload(compare_path, config_path=LANE_CONFIG_PATH)
