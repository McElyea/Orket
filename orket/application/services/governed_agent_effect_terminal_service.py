from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import EffectJournalEntryRecord, OperatorActionRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CheckpointReobservationClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)
from orket_extension_sdk import AgentEffectProposal


async def close_denied_agent_effect(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    proposal: AgentEffectProposal,
    timestamp: str,
    approval_action: OperatorActionRecord,
) -> None:
    run = await execution_repository.get_run_record(run_id=proposal.identity.run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=proposal.identity.attempt_id)
    if run is None or attempt is None:
        raise ValueError("E_AGENT_EFFECT_DENIAL_AUTHORITY_MISSING")
    if (run.current_attempt_id != attempt.attempt_id or attempt.run_id != run.run_id
            or attempt.attempt_state is not AttemptState.EXECUTING
            or run.final_truth_record_id is not None
            or await publication.repository.get_final_truth(run_id=run.run_id) is not None):
        raise ValueError("E_AGENT_TERMINAL_AUTHORITY_CONFLICT")
    actions = await publication.repository.list_operator_actions(target_ref=run.run_id)
    actions = [action for action in actions if approval_action.target_ref in action.receipt_refs
               and action.actor_ref == approval_action.actor_ref and action.timestamp == approval_action.timestamp
               and action.command_class is OperatorCommandClass.MARK_TERMINAL and action.result == "denied"]
    if len(actions) != 1:
        raise ValueError("E_AGENT_EFFECT_DENIAL_OPERATOR_ACTION_MISSING")
    operator_action = actions[0]
    truth = await publication.publish_final_truth(
        final_truth_record_id=f"agent-effect-denial-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.OPERATOR_TERMINAL_STOP,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref=operator_action.action_id,
        operator_action=operator_action,
    )
    attempt = await execution_repository.save_attempt_record(
        record=attempt.model_copy(update={"attempt_state": AttemptState.FAILED, "end_timestamp": timestamp})
    )
    run = await execution_repository.save_run_record(
        record=run.model_copy(
            update={"lifecycle_state": RunState.FAILED_TERMINAL, "final_truth_record_id": truth.final_truth_record_id}
        )
    )


async def reject_denied_agent_checkpoint(publication, checkpoint_id, proposal, timestamp) -> None:
    checkpoint = await publication.repository.get_checkpoint(checkpoint_id=checkpoint_id)
    if checkpoint is None:
        raise ValueError("E_AGENT_EFFECT_CHECKPOINT_MISSING")
    await publication.reject_checkpoint(
        acceptance_id=f"agent-effect-checkpoint-rejection:{proposal.proposal_id}",
        checkpoint=checkpoint,
        supervisor_authority_ref="governed-agent-effect-service:v1",
        decision_timestamp=timestamp,
        required_reobservation_class=CheckpointReobservationClass.NONE,
        integrity_verification_ref=proposal.arguments_digest,
        rejection_reasons=("operator_denied_effect",),
    )


async def mark_uncertain_agent_effect(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    proposal: AgentEffectProposal,
) -> None:
    run = await execution_repository.get_run_record(run_id=proposal.identity.run_id)
    if run is None:
        raise ValueError("E_AGENT_EFFECT_RUN_AUTHORITY_MISSING")
    run = await execution_repository.save_run_record(
        record=run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
    )


async def record_uncertain_agent_effect(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    proposal: AgentEffectProposal,
    timestamp: str,
    authority_ref: str,
) -> EffectJournalEntryRecord:
    journal = await publication.append_effect_journal_entry(
        journal_entry_id=f"agent-effect-journal:{proposal.proposal_id}:{ResidualUncertaintyClassification.UNRESOLVED.value}",
        effect_id=f"agent-effect:{proposal.proposal_id}",
        run_id=proposal.identity.run_id,
        attempt_id=proposal.identity.attempt_id,
        step_id=proposal.identity.step_id,
        authorization_basis_ref=authority_ref,
        publication_timestamp=timestamp,
        intended_target_ref=proposal.intended_target,
        observed_result_ref=None,
        uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        integrity_verification_ref=proposal.arguments_digest,
    )
    await mark_uncertain_agent_effect(
        execution_repository=execution_repository,
        proposal=proposal,
    )
    return journal


__all__ = ["close_denied_agent_effect", "record_uncertain_agent_effect"]
