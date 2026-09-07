from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
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


__all__ = ["close_denied_agent_effect"]
