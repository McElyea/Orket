# LIFECYCLE: live
import json
from pathlib import Path

import pytest

from scripts.odr.context_continuity_inspectability import build_inspectability_payload
from scripts.odr.context_continuity_lane import load_lane_config

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


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_build_inspectability_payload_emits_hashes_and_mode_specific_artifacts() -> None:
    """Layer: contract. Verifies CC-IMP-01 emits hashed per-round artifacts for control, V0, and V1 surfaces."""
    payload = build_inspectability_payload(load_lane_config(LANE_CONFIG_PATH), _load_fixture())

    assert payload["schema_version"] == "odr.context_continuity.inspectability.v1"
    assert payload["artifact_locations"]["inspectability_output"].endswith("context_continuity_inspectability.json")

    by_mode = {row["continuity_mode"]: row for row in payload["scenario_run_artifacts"]}
    assert set(by_mode) == {
        "control_current_replay",
        "v0_log_derived_replay",
        "v1_compiled_shared_state",
    }

    control_round0 = by_mode["control_current_replay"]["round_artifacts"][0]
    assert control_round0["mode_artifacts"]["replay_block"] is None
    assert control_round0["mode_artifacts"]["shared_state_snapshot"] is None
    assert control_round0["role_views"][0]["loaded_context_artifact"]["artifact_sha256"].startswith("sha256:")

    v0_round0 = by_mode["v0_log_derived_replay"]["round_artifacts"][0]
    replay_block = v0_round0["mode_artifacts"]["replay_block"]
    assert replay_block["artifact_sha256"].startswith("sha256:")
    assert replay_block["builder_contract_sha256"].startswith("sha256:")
    assert v0_round0["mode_artifacts"]["replay_block"]["source_history_refs"] == [
        "v0_req_r0",
        "v0_accept_r0",
        "v0_critique_r0",
    ]
    architect_v0_view = next(role_view for role_view in v0_round0["role_views"] if role_view["role"] == "architect")
    assert architect_v0_view["loaded_context_artifact"]["text"].startswith(replay_block["artifact_body"])
    assert architect_v0_view["loaded_context_artifact"]["delivery_mode"] == "replay_block_verbatim_plus_role_focus"
    assert architect_v0_view["loaded_context_artifact"]["replay_block_sha256"] == replay_block["artifact_sha256"]
    assert architect_v0_view["loaded_context_artifact"]["loader_contract_sha256"].startswith("sha256:")

    v1_round0 = by_mode["v1_compiled_shared_state"]["round_artifacts"][0]
    assert v1_round0["mode_artifacts"]["shared_state_snapshot"]["artifact_sha256"].startswith("sha256:")
    assert all(role_view["role_view_projection"] is not None for role_view in v1_round0["role_views"])


def test_build_inspectability_payload_links_predecessors_and_derived_from_inputs() -> None:
    """Layer: contract. Verifies predecessor hashes and explicit derived_from links remain inspectable round to round."""
    payload = build_inspectability_payload(load_lane_config(LANE_CONFIG_PATH), _load_fixture())
    v1_run = next(
        row for row in payload["scenario_run_artifacts"] if row["continuity_mode"] == "v1_compiled_shared_state"
    )

    round0 = v1_run["round_artifacts"][0]
    round1 = v1_run["round_artifacts"][1]
    round0_state_sha = round0["mode_artifacts"]["shared_state_snapshot"]["artifact_sha256"]
    round0_arch_sha = next(
        role_view["loaded_context_artifact"]["artifact_sha256"]
        for role_view in round0["role_views"]
        if role_view["role"] == "architect"
    )
    round1_arch = next(role_view for role_view in round1["role_views"] if role_view["role"] == "architect")

    assert round1["predecessor_linkage"]["prior_round_state_sha256"] == round0_state_sha
    assert round1_arch["predecessor_linkage"]["prior_round_loaded_context_sha256"] == round0_arch_sha
    assert [row["source_input_id"] for row in round1_arch["derived_from"]["source_input_refs"]] == [
        "v1_req_r1",
        "v1_accept_r1",
    ]
    assert [row["artifact_id"] for row in round1_arch["derived_from"]["mode_artifact_refs"]] == ["v1_state_r1"]


def test_build_inspectability_payload_rejects_unknown_source_link() -> None:
    """Layer: contract. Verifies derived_from fails closed when a loaded-context source reference drifts out of inventory."""
    fixture = _load_fixture()
    fixture["scenario_runs"][0]["rounds"][0]["role_views"][0]["derived_from"]["source_input_refs"][0]["source_input_id"] = (
        "missing_source_id"
    )

    with pytest.raises(ValueError, match="unknown source_input_id"):
        build_inspectability_payload(load_lane_config(LANE_CONFIG_PATH), fixture)
