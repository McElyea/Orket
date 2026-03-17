from __future__ import annotations

from orket.runtime.truthful_memory_policy import (
    classify_memory_trust_level,
    evaluate_memory_write_policy,
    render_reference_context_rows,
    synthesis_disposition_for_trust_level,
    truthful_memory_policy_snapshot,
)


# Layer: contract
def test_truthful_memory_policy_snapshot_exposes_phase_d_classes_and_trust_levels() -> None:
    payload = truthful_memory_policy_snapshot()
    assert payload["schema_version"] == "truthful_memory_policy.v1"
    assert set(payload["memory_classes"]) == {"working_memory", "durable_memory", "reference_context"}
    assert set(payload["trust_levels"]) == {"authoritative", "advisory", "stale_risk", "unverified"}


# Layer: contract
def test_truthful_memory_policy_requires_user_correction_for_contradicting_durable_facts() -> None:
    decision = evaluate_memory_write_policy(
        scope="profile_memory",
        key="user_fact.name",
        value="Nova",
        metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:05:00+00:00"},
        existing_value="Aster",
        existing_metadata={"user_confirmed": True, "observed_at": "2026-03-17T14:00:00+00:00"},
    )

    assert decision.allow_write is False
    assert decision.conflict_resolution == "contradiction_requires_correction"
    assert decision.error_code == "E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION"


# Layer: contract
def test_truthful_memory_policy_rejects_stale_durable_updates() -> None:
    decision = evaluate_memory_write_policy(
        scope="profile_memory",
        key="companion_setting.role_id",
        value="planner",
        metadata={"observed_at": "2026-03-17T13:55:00+00:00"},
        existing_value="strategist",
        existing_metadata={"observed_at": "2026-03-17T14:00:00+00:00"},
    )

    assert decision.allow_write is False
    assert decision.conflict_resolution == "stale_update_rejected"
    assert decision.error_code == "E_PROFILE_MEMORY_STALE_UPDATE"


# Layer: contract
def test_truthful_memory_policy_marks_stale_reference_context_as_excluded_from_governed_synthesis() -> None:
    trust_level = classify_memory_trust_level(
        scope="project_memory",
        metadata={"type": "decision", "stale_at": "2000-01-01T00:00:00+00:00"},
        timestamp="2026-03-17T14:00:00+00:00",
    )

    assert trust_level == "stale_risk"
    assert synthesis_disposition_for_trust_level(trust_level) == "exclude"


# Layer: contract
def test_truthful_memory_policy_renders_only_governed_reference_context_rows() -> None:
    rendered = render_reference_context_rows(
        [
            {
                "content": "Use the durable receipt, not narration text.",
                "metadata": {"type": "decision", "trust_level": "advisory"},
                "timestamp": "2026-03-17T14:00:00+00:00",
            },
            {
                "content": "Old stale summary",
                "metadata": {"type": "decision", "stale_at": "2000-01-01T00:00:00+00:00"},
                "timestamp": "2026-03-17T14:00:00+00:00",
            },
        ]
    )

    assert "[reference_context][trust=advisory]" in rendered
    assert "Old stale summary" not in rendered
