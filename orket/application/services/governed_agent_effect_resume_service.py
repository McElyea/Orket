from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_iteration_policy import agent_payload_digest
from orket.application.services.governed_agent_request_builder import build_next_agent_iteration_request
from orket.core.contracts import CheckpointAcceptanceRecord, CheckpointRecord
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentAuthorityGuard,
    GovernedAgentIterationRepository,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    CheckpointAcceptanceOutcome,
    OperatorCommandClass,
    OperatorInputClass,
    ResidualUncertaintyClassification,
    RunState,
)
from orket_extension_sdk import AgentEffectReceipt, AgentIterationRequest, AgentIterationResult

RESUMABLE_AGENT_RULES = frozenset({"effect_approval_required", "accepted_operator_pause", "advisory_pause",
                                 "completion_evidence_insufficient"})


@dataclass(frozen=True, slots=True)
class GovernedAgentResumePreparation:
    request: AgentIterationRequest
    operator_action_ref: str


class GovernedAgentEffectResumeService:
    """Reissues one iteration only after all proposed effects have verified observations."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        iteration_repository: GovernedAgentIterationRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._publication = publication

    async def prepare_resume(
        self,
        *,
        run_id: str,
        effect_receipts: tuple[AgentEffectReceipt, ...],
        accepted_checkpoint_ref: str,
        next_lease_expires_at_utc: str,
        actor_ref: str,
        timestamp: str,
        next_context_inputs: list[dict[str, Any]] | None = None,
    ) -> GovernedAgentResumePreparation:
        run = await self._execution.get_run_record(run_id=run_id)
        if run is None or run.lifecycle_state is not RunState.OPERATOR_BLOCKED:
            raise ValueError("E_AGENT_EFFECT_RESUME_RUN_NOT_BLOCKED")
        current, result = await self._effect_context(run_id)
        _validate_receipts(result, effect_receipts)
        checkpoint, acceptance = await self._accepted_checkpoint(
            result=result,
            checkpoint_ref=accepted_checkpoint_ref,
        )
        next_request = build_next_agent_iteration_request(
            current_request=current,
            accepted_result=result,
            next_lease_expires_at_utc=next_lease_expires_at_utc,
            verification_evidence_ref=accepted_checkpoint_ref,
            next_context_inputs=next_context_inputs,
        )
        payload = next_request.to_wire()
        payload["effect_receipts"] = [receipt.model_dump(mode="json") for receipt in effect_receipts]
        payload["accepted_checkpoint_ref"] = accepted_checkpoint_ref
        next_request = AgentIterationRequest.from_wire(payload)
        request_ref = f"agent-request:{agent_payload_digest(next_request.to_wire())}"
        action = await self._publication.publish_operator_action(
            action_id=f"agent-effect-resume:{run_id}:{next_request.identity.iteration_ordinal}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.COMMAND,
            target_ref=run_id,
            timestamp=timestamp,
            precondition_basis_ref=acceptance.acceptance_id,
            result="resume_authorized",
            command_class=OperatorCommandClass.APPROVE_CONTINUE,
            affected_transition_refs=[],
            affected_resource_refs=[checkpoint.checkpoint_id, request_ref],
            receipt_refs=[receipt.receipt_id for receipt in effect_receipts],
        )
        return GovernedAgentResumePreparation(next_request, action.action_id)

    async def activate_resume(
        self,
        *,
        request: AgentIterationRequest,
        authority_guard: GovernedAgentAuthorityGuard,
    ) -> None:
        run_id = request.identity.run_id
        run = await self._execution.get_run_record(run_id=run_id)
        if run is None or run.lifecycle_state not in {RunState.OPERATOR_BLOCKED, RunState.EXECUTING}:
            raise ValueError("E_AGENT_EFFECT_RESUME_RUN_NOT_BLOCKED")
        _, result = await self._effect_context(run_id)
        _validate_receipts(result, request.effect_receipts)
        if request.accepted_checkpoint_ref is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_CHECKPOINT_UNACCEPTED")
        _, acceptance = await self._accepted_checkpoint(
            result=result,
            checkpoint_ref=request.accepted_checkpoint_ref,
        )
        action = await self._publication.repository.get_operator_action(
            action_id=f"agent-effect-resume:{run_id}:{request.identity.iteration_ordinal}"
        )
        request_ref = f"agent-request:{agent_payload_digest(request.to_wire())}"
        receipt_refs = [receipt.receipt_id for receipt in request.effect_receipts]
        if (
            action is None
            or action.target_ref != run_id
            or action.result != "resume_authorized"
            or action.precondition_basis_ref != acceptance.acceptance_id
            or action.receipt_refs != receipt_refs
            or action.affected_resource_refs != [request.accepted_checkpoint_ref, request_ref]
        ):
            raise ValueError("E_AGENT_EFFECT_RESUME_AUTHORIZATION_MISSING")
        if run.lifecycle_state is RunState.EXECUTING:
            return
        await authority_guard.ensure_active()
        run = await self._execution.save_run_record(
            record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
        )
        await authority_guard.ensure_active()

    async def _effect_context(self, run_id: str) -> tuple[AgentIterationRequest, AgentIterationResult]:
        snapshots = await self._iterations.list_iteration_snapshots(run_id=run_id)
        if not snapshots:
            raise ValueError("E_AGENT_EFFECT_RESUME_ITERATION_MISSING")
        snapshot = max(snapshots, key=lambda item: item.binding.iteration_ordinal)
        if snapshot.result_payload is None or snapshot.decision_payload is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_DECISION_MISSING")
        if (snapshot.decision_payload.get("rule") not in RESUMABLE_AGENT_RULES
                or not snapshot.decision_inputs or not snapshot.decision_inputs.get("valid_recorded_result")):
            raise ValueError("E_AGENT_EFFECT_RESUME_REASON_INVALID")
        return (
            AgentIterationRequest.from_wire(dict(snapshot.request_payload)),
            AgentIterationResult.from_wire(dict(snapshot.result_payload)),
        )

    async def _accepted_checkpoint(
        self,
        *,
        result: AgentIterationResult,
        checkpoint_ref: str,
    ) -> tuple[CheckpointRecord, CheckpointAcceptanceRecord]:
        checkpoint = await self._publication.repository.get_checkpoint(checkpoint_id=checkpoint_ref)
        acceptance = await self._publication.repository.get_checkpoint_acceptance(checkpoint_id=checkpoint_ref)
        expected_effects = {f"agent-effect:{proposal.proposal_id}" for proposal in result.effect_proposals}
        entries = await self._publication.repository.list_effect_journal_entries(run_id=result.identity.run_id)
        accepted_entries = [
            entry for entry in entries if acceptance is not None and entry.journal_entry_id in acceptance.dependent_effect_entry_refs
        ]
        if (
            checkpoint is None
            or acceptance is None
            or checkpoint_ref != f"agent-post-effects-checkpoint:{result.identity.invocation_id}"
            or acceptance.outcome is not CheckpointAcceptanceOutcome.ACCEPTED
            or set(checkpoint.dependent_effect_refs) != expected_effects
            or {entry.effect_id for entry in accepted_entries} != expected_effects
            or any(
                entry.observed_result_ref is None
                or entry.uncertainty_classification is not ResidualUncertaintyClassification.NONE
                for entry in accepted_entries
            )
        ):
            raise ValueError("E_AGENT_EFFECT_RESUME_CHECKPOINT_UNACCEPTED")
        return checkpoint, acceptance


def _validate_receipts(
    result: AgentIterationResult,
    receipts: tuple[AgentEffectReceipt, ...],
) -> None:
    proposals = {proposal.proposal_id: proposal for proposal in result.effect_proposals}
    received = {receipt.proposal_id: receipt for receipt in receipts}
    if set(proposals) != set(received):
        raise ValueError("E_AGENT_EFFECT_RESUME_RECEIPTS_INCOMPLETE")
    for proposal_id, proposal in proposals.items():
        receipt = received[proposal_id]
        if receipt.identity != proposal.identity or receipt.arguments_digest != proposal.arguments_digest:
            raise ValueError("E_AGENT_EFFECT_RESUME_RECEIPT_DRIFT")
        if receipt.state not in {"observed", "reconciled"}:
            raise ValueError("E_AGENT_EFFECT_RESUME_RECEIPT_UNSAFE")


__all__ = ["GovernedAgentEffectResumeService", "GovernedAgentResumePreparation"]
