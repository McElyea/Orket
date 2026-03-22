from pathlib import Path

from scripts.odr.context_continuity_v1_state import (
    build_v1_role_view,
    build_v1_shared_state,
    compute_v1_continuity_run_metrics,
    normalize_identity_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
V1_CONTRACT_PATH = (
    REPO_ROOT
    / "docs"
    / "projects"
    / "archive"
    / "ContextContinuity"
    / "CC03212026"
    / "odr_context_continuity_v1_state_contract.json"
)


def test_normalize_identity_text_stays_exact_and_non_fuzzy() -> None:
    """Layer: unit. Verifies V1 item identity uses exact normalized text rather than semantic equivalence."""
    assert normalize_identity_text("- Preserve user edits.") == "preserve user edits"
    assert normalize_identity_text("Store notes locally only.") != normalize_identity_text("Persist notes on-device only.")


def test_build_v1_shared_state_preserves_accepted_items_and_records_reopen_events() -> None:
    """Layer: contract. Verifies V1 keeps prior accepted items authoritative while recording unauthorized reopen/regression events."""
    round0 = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r0",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": "Preserve user edits. Store notes locally only.",
            }
        ],
        current_requirement="Preserve user edits. Store notes locally only.",
        round_index=0,
        artifact_id="state_r0",
        contract_path=V1_CONTRACT_PATH,
    )
    round1 = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r1",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": "Store notes locally only.",
            }
        ],
        current_requirement="Store notes locally only.",
        round_index=1,
        artifact_id="state_r1",
        latest_trace={"pending_decisions": ["Preserve user edits."], "contradiction_count": 1},
        prior_state_payload=round0["payload"],
        contract_path=V1_CONTRACT_PATH,
    )

    payload = round1["payload"]
    accepted_texts = {row["text"] for row in payload["accepted_items"]}
    assert "Preserve user edits." in accepted_texts
    assert "Store notes locally only." in accepted_texts
    assert len(payload["transition_events"]["reopened"]) == 1
    assert len(payload["transition_events"]["regressions"]) == 1
    assert len(payload["transition_events"]["contradictions"]) == 1


def test_build_v1_role_view_projects_shared_state_verbatim_with_role_focus() -> None:
    """Layer: contract. Verifies V1 role views derive prompt-ready context directly from the shared-state snapshot."""
    shared_state = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r0",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": "Preserve user edits. Store notes locally only.",
            },
            {
                "artifact_id": "crit_r0",
                "artifact_kind": "latest_auditor_critique",
                "artifact_body": "Clarify restart survival.",
            },
        ],
        current_requirement="Preserve user edits. Store notes locally only.",
        round_index=0,
        artifact_id="state_r0",
        contract_path=V1_CONTRACT_PATH,
    )

    role_view = build_v1_role_view(
        {"artifact_id": "state_r0", "artifact_sha256": "sha256:test", "artifact_body": shared_state["payload"]},
        role="architect",
        role_focus="Refine restart survival without reopening accepted storage scope.",
        contract_path=V1_CONTRACT_PATH,
    )

    assert role_view["projection_text"].startswith("### SHARED STATE")
    assert "#### Accepted Decisions" in role_view["projection_text"]
    assert "#### Role Focus" in role_view["loaded_context"]
    assert role_view["delivery_mode"] == "compiled_state_projection_verbatim_plus_role_focus"


def test_compute_v1_continuity_run_metrics_uses_state_history() -> None:
    """Layer: unit. Verifies V1 metrics are computed from compiled-state events and preserved accepted-item ids."""
    round0 = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r0",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": "Preserve user edits. Store notes locally only.",
            }
        ],
        current_requirement="Preserve user edits. Store notes locally only.",
        round_index=0,
        artifact_id="state_r0",
        contract_path=V1_CONTRACT_PATH,
    )
    round1 = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r1",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": "Store notes locally only.",
            }
        ],
        current_requirement="Store notes locally only.",
        round_index=1,
        artifact_id="state_r1",
        latest_trace={"pending_decisions": ["Preserve user edits."], "contradiction_count": 1},
        prior_state_payload=round0["payload"],
        contract_path=V1_CONTRACT_PATH,
    )

    metrics = compute_v1_continuity_run_metrics(
        [
            {"artifact_body": round0["payload"]},
            {"artifact_body": round1["payload"]},
        ]
    )

    assert metrics == {
        "reopened_decision_count": 1,
        "contradiction_count": 1,
        "regression_count": 1,
        "carry_forward_integrity": 1.0,
    }


def test_build_v1_shared_state_keeps_explicit_unresolved_and_constraint_categories() -> None:
    """Layer: contract. Verifies V1 preserves explicit unresolved summaries and maps fenced constraint categories into accepted, rejected, and invariant state without JSON-fragment drift."""
    requirement = """# Requirement Spec

## Invariants
- User profile data remains local.

```orket-constraints
{
  "must_have": [
    {"id": "MH-LOCAL-001", "text": "Store user profile data locally."}
  ],
  "forbidden": [
    {"id": "FB-CLOUD-001", "text": "Upload profile data to external services."}
  ]
}
```
"""
    state = build_v1_shared_state(
        source_inputs=[
            {
                "artifact_id": "req_r0",
                "artifact_kind": "current_canonical_artifact",
                "artifact_body": requirement,
            },
            {
                "artifact_id": "unresolved_r0",
                "artifact_kind": "unresolved_issue_summary",
                "artifact_body": "AUD-001: Add retention policy",
            },
        ],
        current_requirement=requirement,
        round_index=0,
        artifact_id="state_r0",
        contract_path=V1_CONTRACT_PATH,
    )

    payload = state["payload"]
    assert [row["text"] for row in payload["accepted_items"]] == ["Store user profile data locally."]
    assert [row["text"] for row in payload["rejected_items"]] == ["Upload profile data to external services."]
    assert [row["text"] for row in payload["unresolved_items"]] == ["AUD-001: Add retention policy"]
    assert [row["text"] for row in payload["invariants"]] == ["User profile data remains local."]
