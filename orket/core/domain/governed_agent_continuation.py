from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

AgentContinuationDisposition = Literal[
    "continue",
    "pause",
    "complete",
    "cancelled",
    "blocked",
    "failed",
    "recover",
]
AgentRecommendation = Literal["continue", "pause", "stop", "complete"]


@dataclass(frozen=True, slots=True)
class GovernedAgentContinuationInputs:
    valid_recorded_result: bool
    effect_approval_required: bool
    unresolved_effect_boundary: bool
    policy_violation: bool
    quarantine_required: bool
    accepted_cancel: bool
    accepted_terminal_stop: bool
    verified_objective_satisfied: bool
    verification_evidence_sufficient: bool
    deadline_expired: bool
    lease_expired: bool
    capability_budget_exhausted: bool
    effect_budget_exhausted: bool
    iteration_budget_exhausted: bool
    model_budget_exhausted: bool
    token_budget_exhausted: bool
    output_budget_exhausted: bool
    artifact_budget_exhausted: bool
    unrecoverable_execution_failure: bool
    repeated_state_threshold_hit: bool
    no_progress_threshold_hit: bool
    extension_recommendation: AgentRecommendation
    progress_projection_version: str = "governed_agent_progress.v1"
    progress_projection_digest: str | None = None
    repeated_state_count: int = 0
    no_progress_count: int = 0
    accepted_pause: bool = False
    operator_action_refs: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GovernedAgentContinuationDecision:
    policy_version: Literal["governed_agent_continuation.v1"]
    disposition: AgentContinuationDisposition
    next_iteration_authorized: bool
    safe_to_continue: bool
    rule: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def decide_governed_agent_continuation(
    inputs: GovernedAgentContinuationInputs,
) -> GovernedAgentContinuationDecision:
    """Apply the durable V1 stop priority without consulting ambient state."""
    if inputs.unresolved_effect_boundary or inputs.policy_violation or inputs.quarantine_required:
        return _decision("recover", "unsafe_or_unresolved_boundary")
    if inputs.accepted_cancel:
        return _decision("cancelled", "accepted_cancel")
    if inputs.accepted_terminal_stop:
        return _decision("blocked", "accepted_terminal_stop")
    if inputs.effect_approval_required:
        return _decision("pause", "effect_approval_required")
    if inputs.accepted_pause:
        return _decision("pause", "accepted_operator_pause")
    if inputs.verified_objective_satisfied and inputs.verification_evidence_sufficient:
        return _decision("complete", "verified_objective_satisfied")
    if inputs.deadline_expired or inputs.lease_expired:
        return _decision("blocked", "time_budget_exhausted")
    if inputs.capability_budget_exhausted or inputs.effect_budget_exhausted:
        return _decision("blocked", "capability_budget_exhausted")
    if (
        inputs.iteration_budget_exhausted
        or inputs.model_budget_exhausted
        or inputs.token_budget_exhausted
        or inputs.output_budget_exhausted
        or inputs.artifact_budget_exhausted
    ):
        return _decision("blocked", "execution_budget_exhausted")
    if inputs.unrecoverable_execution_failure or not inputs.valid_recorded_result:
        return _decision("failed", "unrecoverable_or_invalid_result")
    if inputs.repeated_state_threshold_hit or inputs.no_progress_threshold_hit:
        return _decision("blocked", "progress_threshold_exhausted")
    if inputs.extension_recommendation == "continue":
        return _decision("continue", "advisory_continue_admitted")
    if inputs.extension_recommendation == "pause":
        return _decision("pause", "advisory_pause")
    if inputs.extension_recommendation == "stop":
        return _decision("blocked", "advisory_stop")
    return _decision("pause", "completion_evidence_insufficient")


def _decision(
    disposition: AgentContinuationDisposition,
    rule: str,
) -> GovernedAgentContinuationDecision:
    continuing = disposition == "continue"
    return GovernedAgentContinuationDecision(
        policy_version="governed_agent_continuation.v1",
        disposition=disposition,
        next_iteration_authorized=continuing,
        safe_to_continue=continuing,
        rule=rule,
    )
