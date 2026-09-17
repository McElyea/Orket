from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_authority import ensure_governed_agent_authority
from orket.application.services.governed_agent_iteration_policy import GovernedAgentVerificationObservation
from orket.core.contracts import AttemptRecord, FinalTruthRecord, RunRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityGuard
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)
from orket.core.domain.governed_agent_continuation import GovernedAgentContinuationDecision


async def close_agent_run(
    *, transactions: ControlPlaneTransactionFactory,
    guard: GovernedAgentAuthorityGuard | None, run: RunRecord, attempt: AttemptRecord,
    decision: GovernedAgentContinuationDecision, verification: GovernedAgentVerificationObservation,
    decision_ref: str, end_timestamp: str,
    invocation_id: str, operator_action_refs: tuple[str, ...],
) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord]:
    await ensure_governed_agent_authority(guard)
    async with transactions() as transaction:
        current_run = await transaction.execution.get_run_record(run_id=run.run_id)
        current_attempt = await transaction.execution.get_attempt_record(attempt_id=attempt.attempt_id)
        existing_truth = await transaction.records.get_final_truth(run_id=run.run_id)
        if current_run != run or current_attempt != attempt or existing_truth is not None:
            raise ValueError("E_AGENT_TERMINAL_AUTHORITY_CONFLICT")
        success = decision.disposition == "complete"
        operator_stop = decision.rule == "accepted_terminal_stop"
        if decision.disposition not in {"complete", "blocked", "failed"}:
            raise ValueError("E_AGENT_NONTERMINAL_DECISION")
        operator_action = None
        if operator_stop:
            actions = [await transaction.records.get_operator_action(action_id=ref) for ref in operator_action_refs]
            stops = [action for action in actions if action is not None and action.target_ref == run.run_id
                     and action.precondition_basis_ref == f"agent-control:{invocation_id}"
                     and action.command_class is OperatorCommandClass.MARK_TERMINAL]
            if len(stops) != 1:
                raise ValueError("E_AGENT_TERMINAL_OPERATOR_ACTION_MISSING")
            operator_action = stops[0]
        await ensure_governed_agent_authority(guard)
        truth = await ControlPlanePublicationService(repository=transaction.records).publish_final_truth(
            final_truth_record_id=f"agent-final-truth:{run.run_id}", run_id=run.run_id,
            result_class=ResultClass.SUCCESS if success else ResultClass.FAILED if decision.disposition == "failed"
            else ResultClass.BLOCKED,
            completion_classification=CompletionClassification.SATISFIED if success else CompletionClassification.UNSATISFIED,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.NORMAL_EXECUTION if success else
            ClosureBasisClassification.OPERATOR_TERMINAL_STOP if operator_stop else ClosureBasisClassification.POLICY_TERMINAL_STOP,
            authority_sources=[AuthoritySourceClass.VALIDATED_ARTIFACT if success else AuthoritySourceClass.RECEIPT_EVIDENCE],
            authoritative_result_ref=verification.authoritative_result_ref if success else decision_ref,
            operator_action=operator_action,
        )
        await ensure_governed_agent_authority(guard)
        attempt = await transaction.execution.save_attempt_record(record=attempt.model_copy(update={
            "attempt_state": AttemptState.COMPLETED if success else AttemptState.FAILED, "end_timestamp": end_timestamp,
        }))
        await ensure_governed_agent_authority(guard)
        run = await transaction.execution.save_run_record(record=run.model_copy(update={
            "lifecycle_state": RunState.COMPLETED if success else RunState.FAILED_TERMINAL,
            "final_truth_record_id": truth.final_truth_record_id,
        }))
        await ensure_governed_agent_authority(guard)
        return run, attempt, truth
