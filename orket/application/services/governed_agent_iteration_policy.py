from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from orket.application.services.governed_agent_ports import GovernedAgentInvocationBinding
from orket.core.domain.governed_agent_continuation import GovernedAgentContinuationInputs
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult, canonical_digest_sha256


@dataclass(frozen=True, slots=True)
class GovernedAgentVerificationObservation:
    verifier_id: str
    verifier_version: str
    output_admissible: bool
    objective_satisfied: bool
    evidence_sufficient: bool
    evidence_ref: str
    authoritative_result_ref: str | None


def agent_invocation_binding(
    request: AgentIterationRequest,
    extension_digest: str,
) -> GovernedAgentInvocationBinding:
    identity = request.identity
    return GovernedAgentInvocationBinding(
        run_id=identity.run_id,
        attempt_id=identity.attempt_id,
        step_id=identity.step_id,
        iteration_ordinal=identity.iteration_ordinal,
        invocation_id=identity.invocation_id,
        fencing_generation=identity.fencing_generation,
        cancellation_epoch=request.cancellation.cancellation_epoch,
        deadline_utc=request.deadline_utc,
        extension_digest=extension_digest,
        policy_digest=request.policy_digest,
        request_digest=agent_payload_digest(request.to_wire()),
    )


def continuation_inputs(
    *,
    request: AgentIterationRequest,
    result: AgentIterationResult,
    verification: GovernedAgentVerificationObservation,
    decision_timestamp_utc: str,
) -> GovernedAgentContinuationInputs:
    timestamp = datetime.fromisoformat(decision_timestamp_utc.replace("Z", "+00:00"))
    deadline = datetime.fromisoformat(request.deadline_utc.replace("Z", "+00:00"))
    lease_expiry = datetime.fromisoformat(request.lease_expires_at_utc.replace("Z", "+00:00"))
    usage = result.usage
    budget = request.remaining_run_budget
    return GovernedAgentContinuationInputs(
        valid_recorded_result=verification.output_admissible,
        effect_approval_required=bool(result.effect_proposals),
        unresolved_effect_boundary=any(receipt.state == "uncertain" for receipt in request.effect_receipts),
        policy_violation=False,
        quarantine_required=False,
        accepted_cancel=request.cancellation.requested,
        accepted_terminal_stop=False,
        verified_objective_satisfied=verification.objective_satisfied,
        verification_evidence_sufficient=verification.evidence_sufficient,
        deadline_expired=timestamp >= deadline,
        lease_expired=timestamp >= lease_expiry,
        capability_budget_exhausted=False,
        effect_budget_exhausted=usage.effect_proposals >= budget.effect_proposals,
        iteration_budget_exhausted=budget.iterations <= 1,
        model_budget_exhausted=usage.model_calls >= budget.model_calls,
        token_budget_exhausted=(
            usage.charged_input_tokens >= budget.input_tokens
            or usage.charged_output_tokens >= budget.output_tokens
        ),
        output_budget_exhausted=usage.output_bytes >= budget.output_bytes,
        artifact_budget_exhausted=usage.artifact_bytes >= budget.artifact_bytes,
        unrecoverable_execution_failure=result.invocation_status == "failed",
        repeated_state_threshold_hit=False,
        no_progress_threshold_hit=False,
        extension_recommendation=result.completion_recommendation,
    )


def agent_payload_digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(dict(payload)))
