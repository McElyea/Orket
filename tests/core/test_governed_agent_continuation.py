# Layer: unit

from __future__ import annotations

from dataclasses import replace

from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)


def _inputs() -> GovernedAgentContinuationInputs:
    return GovernedAgentContinuationInputs(
        valid_recorded_result=True,
        effect_approval_required=False,
        unresolved_effect_boundary=False,
        policy_violation=False,
        quarantine_required=False,
        accepted_cancel=False,
        accepted_terminal_stop=False,
        verified_objective_satisfied=False,
        verification_evidence_sufficient=False,
        deadline_expired=False,
        lease_expired=False,
        capability_budget_exhausted=False,
        effect_budget_exhausted=False,
        iteration_budget_exhausted=False,
        model_budget_exhausted=False,
        token_budget_exhausted=False,
        output_budget_exhausted=False,
        artifact_budget_exhausted=False,
        unrecoverable_execution_failure=False,
        repeated_state_threshold_hit=False,
        no_progress_threshold_hit=False,
        extension_recommendation="continue",
    )


def test_continuation_requires_recorded_safe_inputs() -> None:
    decision = decide_governed_agent_continuation(_inputs())

    assert decision.disposition == "continue"
    assert decision.next_iteration_authorized is True
    assert decision.safe_to_continue is True


def test_stop_priority_places_uncertainty_and_cancel_before_verified_completion() -> None:
    satisfied = replace(
        _inputs(),
        verified_objective_satisfied=True,
        verification_evidence_sufficient=True,
    )

    assert decide_governed_agent_continuation(satisfied).disposition == "complete"
    assert decide_governed_agent_continuation(
        replace(satisfied, accepted_cancel=True)
    ).disposition == "cancelled"
    assert decide_governed_agent_continuation(
        replace(satisfied, accepted_cancel=True, unresolved_effect_boundary=True)
    ).disposition == "recover"


def test_unverified_completion_recommendation_cannot_publish_success() -> None:
    decision = decide_governed_agent_continuation(
        replace(_inputs(), extension_recommendation="complete")
    )

    assert decision.disposition == "pause"
    assert decision.next_iteration_authorized is False
