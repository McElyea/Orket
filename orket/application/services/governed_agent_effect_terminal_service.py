from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import EffectJournalEntryRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
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
) -> None:
    run = await execution_repository.get_run_record(run_id=proposal.identity.run_id)
    attempt = await execution_repository.get_attempt_record(attempt_id=proposal.identity.attempt_id)
    if run is None or attempt is None:
        raise ValueError("E_AGENT_EFFECT_DENIAL_AUTHORITY_MISSING")
    actions = await publication.repository.list_operator_actions(target_ref=run.run_id)
    if not actions:
        raise ValueError("E_AGENT_EFFECT_DENIAL_OPERATOR_ACTION_MISSING")
    operator_action = actions[-1]
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
    await execution_repository.save_attempt_record(
        record=attempt.model_copy(update={"attempt_state": AttemptState.FAILED, "end_timestamp": timestamp})
    )
    await execution_repository.save_run_record(
        record=run.model_copy(
            update={"lifecycle_state": RunState.FAILED_TERMINAL, "final_truth_record_id": truth.final_truth_record_id}
        )
    )


async def mark_uncertain_agent_effect(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    proposal: AgentEffectProposal,
) -> None:
    run = await execution_repository.get_run_record(run_id=proposal.identity.run_id)
    if run is None:
        raise ValueError("E_AGENT_EFFECT_RUN_AUTHORITY_MISSING")
    await execution_repository.save_run_record(
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
