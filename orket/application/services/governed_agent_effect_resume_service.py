from __future__ import annotations

from dataclasses import dataclass

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_ports import GovernedAgentIterationRepository
from orket.application.services.governed_agent_request_builder import build_next_agent_iteration_request
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import OperatorCommandClass, OperatorInputClass, RunState
from orket_extension_sdk import AgentEffectReceipt, AgentIterationRequest, AgentIterationResult


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
    ) -> GovernedAgentResumePreparation:
        run = await self._execution.get_run_record(run_id=run_id)
        if run is None or run.lifecycle_state is not RunState.OPERATOR_BLOCKED:
            raise ValueError("E_AGENT_EFFECT_RESUME_RUN_NOT_BLOCKED")
        snapshots = await self._iterations.list_iteration_snapshots(run_id=run_id)
        if not snapshots:
            raise ValueError("E_AGENT_EFFECT_RESUME_ITERATION_MISSING")
        snapshot = max(snapshots, key=lambda item: item.binding.iteration_ordinal)
        if snapshot.result_payload is None or snapshot.decision_payload is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_DECISION_MISSING")
        if snapshot.decision_payload.get("rule") != "effect_approval_required":
            raise ValueError("E_AGENT_EFFECT_RESUME_REASON_INVALID")
        current = AgentIterationRequest.from_wire(snapshot.request_payload)
        result = AgentIterationResult.from_wire(snapshot.result_payload)
        _validate_receipts(result, effect_receipts)
        checkpoint = await self._publication.repository.get_checkpoint(
            checkpoint_id=accepted_checkpoint_ref
        )
        acceptance = await self._publication.repository.get_checkpoint_acceptance(
            checkpoint_id=accepted_checkpoint_ref
        )
        if checkpoint is None or acceptance is None:
            raise ValueError("E_AGENT_EFFECT_RESUME_CHECKPOINT_UNACCEPTED")
        next_request = build_next_agent_iteration_request(
            current_request=current,
            accepted_result=result,
            next_lease_expires_at_utc=next_lease_expires_at_utc,
            verification_evidence_ref=accepted_checkpoint_ref,
        )
        payload = next_request.to_wire()
        payload["effect_receipts"] = [receipt.model_dump(mode="json") for receipt in effect_receipts]
        payload["accepted_checkpoint_ref"] = accepted_checkpoint_ref
        next_request = AgentIterationRequest.from_wire(payload)
        action = await self._publication.publish_operator_action(
            action_id=f"agent-effect-resume:{run_id}:{next_request.identity.iteration_ordinal}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.COMMAND,
            target_ref=run_id,
            timestamp=timestamp,
            precondition_basis_ref=acceptance.acceptance_id,
            result="resumed",
            command_class=OperatorCommandClass.APPROVE_CONTINUE,
            affected_transition_refs=[f"{run_id}:operator_blocked->executing"],
            affected_resource_refs=[checkpoint.checkpoint_id],
            receipt_refs=[receipt.receipt_id for receipt in effect_receipts],
        )
        await self._execution.save_run_record(
            record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
        )
        return GovernedAgentResumePreparation(next_request, action.action_id)


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
