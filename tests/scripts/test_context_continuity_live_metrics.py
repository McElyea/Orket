from scripts.odr.context_continuity_live_metrics import (
    accepted_decision_summaries,
    build_replay_source_history,
    compute_continuity_run_metrics,
    invariant_summaries,
    rejected_path_summaries,
)


def test_build_replay_source_history_emits_bounded_authoritative_items() -> None:
    """Layer: unit. Verifies V0 live proof history building stays within the locked authoritative source kinds."""
    rows = build_replay_source_history(
        scenario_input={"A0": [{"id": "I1", "required_action": "resolve restart persistence"}]},
        current_requirement="The assistant must preserve edits and must store notes locally.",
        prior_auditor_output="Clarify restart persistence.",
        latest_trace={
            "pending_decisions": ["DECISION_REQUIRED(restart_scope)"],
            "architect_parsed": {"changelog": ["Added local-only persistence requirement."]},
        },
        round_index=0,
    )

    assert rows[0]["artifact_kind"] == "current_canonical_artifact"
    assert any(row["artifact_kind"] == "accepted_decision_summary" for row in rows)
    assert any(row["artifact_kind"] == "unresolved_issue_summary" for row in rows)
    assert any(row["artifact_kind"] == "latest_auditor_critique" for row in rows)
    assert any(row["artifact_kind"] == "latest_architect_delta" for row in rows)


def test_compute_continuity_run_metrics_counts_reopened_and_regression_events() -> None:
    """Layer: unit. Verifies live continuity metrics count reopened, contradiction, regression, and carry-forward deterministically."""
    metrics = compute_continuity_run_metrics(
        [
            {
                "trace": {
                    "pending_decision_count": 0,
                    "contradiction_count": 0,
                    "required_constraint_regressions": [],
                    "constraint_demotion_violations": [],
                    "architect_parsed": {"requirement": "The assistant must preserve edits."},
                }
            },
            {
                "trace": {
                    "pending_decision_count": 1,
                    "contradiction_count": 1,
                    "required_constraint_regressions": ["The assistant must preserve edits"],
                    "constraint_demotion_violations": [],
                    "architect_parsed": {"requirement": "The assistant uses DECISION_REQUIRED(restart_scope)."},
                }
            },
        ],
        final_requirement="The assistant uses DECISION_REQUIRED(restart_scope).",
    )

    assert metrics == {
        "reopened_decision_count": 1,
        "contradiction_count": 1,
        "regression_count": 1,
        "carry_forward_integrity": 0.0,
    }


def test_requirement_summary_extractors_ignore_constraint_json_fragments() -> None:
    """Layer: unit. Verifies live metric summary extraction uses the fenced constraint payload and invariant section text instead of JSON key fragments."""
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

    assert accepted_decision_summaries(requirement) == ["Store user profile data locally."]
    assert rejected_path_summaries(requirement) == ["Upload profile data to external services."]
    assert invariant_summaries(requirement) == ["User profile data remains local."]
