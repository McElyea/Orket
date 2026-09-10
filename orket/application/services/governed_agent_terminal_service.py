from __future__ import annotations

from typing import Protocol

from orket.application.services.governed_agent_iteration_policy import GovernedAgentVerificationObservation
from orket.application.services.governed_agent_ports import GovernedAgentAuthorityGuard, ensure_governed_agent_authority
from orket.core.contracts import AttemptRecord, FinalTruthRecord, RunRecord
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
    TerminalityBasisClassification,
)
from orket.core.domain.governed_agent_continuation import GovernedAgentContinuationDecision


class GovernedAgentFinalTruthRepository(Protocol):
    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord: ...

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None: ...


async def close_agent_run(
    *, execution: ControlPlaneExecutionRepository, truth_repository: GovernedAgentFinalTruthRepository,
    guard: GovernedAgentAuthorityGuard | None, run: RunRecord, attempt: AttemptRecord,
    decision: GovernedAgentContinuationDecision, verification: GovernedAgentVerificationObservation,
    decision_ref: str, end_timestamp: str,
) -> tuple[RunRecord, AttemptRecord, FinalTruthRecord]:
    success = decision.disposition == "complete"
    operator_stop = decision.rule == "accepted_terminal_stop"
    if decision.disposition not in {"complete", "blocked", "failed"}:
        raise ValueError("E_AGENT_NONTERMINAL_DECISION")
    await ensure_governed_agent_authority(guard)
    truth = await truth_repository.save_final_truth(record=FinalTruthRecord(
        final_truth_record_id=f"agent-final-truth:{run.run_id}", run_id=run.run_id,
        result_class=ResultClass.SUCCESS if success else ResultClass.FAILED if decision.disposition == "failed"
        else ResultClass.BLOCKED,
        completion_classification=CompletionClassification.SATISFIED if success else CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION if success else
        ClosureBasisClassification.OPERATOR_TERMINAL_STOP if operator_stop else ClosureBasisClassification.POLICY_TERMINAL_STOP,
        terminality_basis=TerminalityBasisClassification.COMPLETED_TERMINAL if success else
        TerminalityBasisClassification.OPERATOR_TERMINAL if operator_stop else TerminalityBasisClassification.POLICY_TERMINAL,
        authority_sources=[AuthoritySourceClass.VALIDATED_ARTIFACT if success else AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref=verification.authoritative_result_ref if success else decision_ref,
    ))
    await ensure_governed_agent_authority(guard)
    attempt = await execution.save_attempt_record(record=attempt.model_copy(update={
        "attempt_state": AttemptState.COMPLETED if success else AttemptState.FAILED, "end_timestamp": end_timestamp,
    }))
    await ensure_governed_agent_authority(guard)
    run = await execution.save_run_record(record=run.model_copy(update={
        "lifecycle_state": RunState.COMPLETED if success else RunState.FAILED_TERMINAL,
        "final_truth_record_id": truth.final_truth_record_id,
    }))
    return run, attempt, truth
