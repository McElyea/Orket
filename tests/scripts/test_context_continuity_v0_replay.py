# LIFECYCLE: live
from pathlib import Path

import pytest

from scripts.odr.context_continuity_v0_replay import build_v0_loaded_context, build_v0_replay_block

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


def test_build_v0_replay_block_is_deterministic_and_suppresses_duplicates() -> None:
    """Layer: contract. Verifies V0 replay ordering is deterministic and duplicate items collapse to the newest evidence."""
    source_history = [
        {
            "artifact_id": "accept_old",
            "artifact_kind": "accepted_decision_summary",
            "authority_level": "authoritative",
            "content": "Persistence is local-only.",
            "round_index": 0,
        },
        {
            "artifact_id": "audit_1",
            "artifact_kind": "latest_auditor_critique",
            "authority_level": "authoritative",
            "content": "Clarify restart persistence.",
            "round_index": 1,
        },
        {
            "artifact_id": "arch_1",
            "artifact_kind": "latest_architect_delta",
            "authority_level": "authoritative",
            "content": "Added restart restoration requirement.",
            "round_index": 1,
        },
        {
            "artifact_id": "current_1",
            "artifact_kind": "current_canonical_artifact",
            "authority_level": "authoritative",
            "content": "Restore the last saved note after restart.",
            "round_index": 1,
        },
        {
            "artifact_id": "accept_new",
            "artifact_kind": "accepted_decision_summary",
            "authority_level": "authoritative",
            "content": "Persistence is local-only.",
            "round_index": 1,
        },
    ]

    replay_one = build_v0_replay_block(source_history, artifact_id="replay_a", config_path=LANE_CONFIG_PATH)
    replay_two = build_v0_replay_block(list(reversed(source_history)), artifact_id="replay_a", config_path=LANE_CONFIG_PATH)

    assert replay_one["content"] == replay_two["content"]
    assert replay_one["source_history_refs"] == ["current_1", "accept_new", "arch_1", "audit_1"]
    assert "#### Current Artifact" in replay_one["content"]
    assert "#### Accepted Decisions" in replay_one["content"]
    assert "#### Latest Architect Delta" in replay_one["content"]
    assert "#### Latest Auditor Critique" in replay_one["content"]
    assert "#### Causal Summary" in replay_one["content"]
    assert "accept_old" not in replay_one["source_history_refs"]


def test_build_v0_replay_block_truncates_low_precedence_sections_before_required_context() -> None:
    """Layer: contract. Verifies truncation drops lower-precedence replay inputs before the required current artifact."""
    noisy_unresolved = "Unresolved detail " + ("x" * 260)
    source_history = [
        {
            "artifact_id": "current_1",
            "artifact_kind": "current_canonical_artifact",
            "authority_level": "authoritative",
            "content": "Restore the last saved note after restart.",
            "round_index": 1,
        },
        *[
            {
                "artifact_id": f"issue_{index}",
                "artifact_kind": "unresolved_issue_summary",
                "authority_level": "authoritative",
                "content": f"{noisy_unresolved} #{index}",
                "round_index": 1,
            }
            for index in range(6)
        ],
    ]

    replay = build_v0_replay_block(source_history, artifact_id="replay_b", config_path=LANE_CONFIG_PATH)

    assert len(replay["content"].encode("utf-8")) <= 1200
    assert "Restore the last saved note after restart." in replay["content"]
    assert replay["source_history_refs"][0] == "current_1"
    assert len([ref for ref in replay["source_history_refs"] if ref.startswith("issue_")]) < 6


def test_build_v0_replay_block_rejects_excluded_source_kind() -> None:
    """Layer: contract. Verifies V0 fails closed if compiled-state artifacts try to enter the bounded replay path."""
    source_history = [
        {
            "artifact_id": "state_1",
            "artifact_kind": "compiled_shared_state",
            "authority_level": "authoritative",
            "payload": {"accepted": ["x"]},
            "round_index": 1,
        }
    ]

    with pytest.raises(ValueError, match="explicitly excluded"):
        build_v0_replay_block(source_history, artifact_id="replay_c", config_path=LANE_CONFIG_PATH)


def test_build_v0_loaded_context_embeds_replay_block_verbatim() -> None:
    """Layer: contract. Verifies the V0 loader delivers the replay block itself, not only a paraphrased projection."""
    replay_block = build_v0_replay_block(
        [
            {
                "artifact_id": "current_1",
                "artifact_kind": "current_canonical_artifact",
                "authority_level": "authoritative",
                "content": "Restore the last saved note after restart.",
                "round_index": 1,
            },
            {
                "artifact_id": "accept_1",
                "artifact_kind": "accepted_decision_summary",
                "authority_level": "authoritative",
                "content": "Persistence is local-only.",
                "round_index": 1,
            },
        ],
        artifact_id="replay_d",
        config_path=LANE_CONFIG_PATH,
    )

    loaded = build_v0_loaded_context(replay_block, role="architect", config_path=LANE_CONFIG_PATH)

    assert loaded["text"].startswith(replay_block["content"])
    assert "#### Role Focus" in loaded["text"]
    assert loaded["delivery_mode"] == "replay_block_verbatim_plus_role_focus"
    assert loaded["replay_block_sha256"] == replay_block["artifact_sha256"]
    assert loaded["loader_contract_sha256"].startswith("sha256:")
