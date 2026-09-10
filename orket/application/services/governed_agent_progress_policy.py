from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from orket.application.services.governed_agent_iteration_policy import GovernedAgentVerificationObservation
from orket.application.services.governed_agent_ports import GovernedAgentIterationSnapshot
from orket.core.domain.governed_agent_continuation import GovernedAgentContinuationInputs
from orket_extension_sdk import AgentIterationRequest


def with_recorded_progress(
    inputs: GovernedAgentContinuationInputs,
    request: AgentIterationRequest,
    verification: GovernedAgentVerificationObservation,
    history: Sequence[GovernedAgentIterationSnapshot],
) -> GovernedAgentContinuationInputs:
    """Host verifier projections determine progress; model progress claims never reset it."""
    previous = [snapshot.decision_inputs for snapshot in sorted(history, key=lambda item: item.binding.iteration_ordinal)
                if snapshot.binding.iteration_ordinal < request.identity.iteration_ordinal
                and snapshot.decision_inputs is not None]
    digest = verification.progress_projection_digest if verification.output_admissible else None
    last = previous[-1] if previous else {}
    repeated = sum(item.get("progress_projection_digest") == digest for item in previous) if digest else 0
    progressed = digest is not None and digest != last.get("progress_projection_digest")
    no_progress = 0 if progressed else int(last.get("no_progress_count", 0)) + 1
    budget = request.remaining_run_budget
    return replace(
        inputs,
        progress_projection_digest=digest,
        repeated_state_count=repeated,
        no_progress_count=no_progress,
        repeated_state_threshold_hit=repeated >= budget.repeated_states,
        no_progress_threshold_hit=no_progress >= budget.no_progress_iterations,
    )
