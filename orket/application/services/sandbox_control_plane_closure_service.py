from __future__ import annotations

from dataclasses import dataclass

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import FinalTruthRecord, ReconciliationRecord
from orket.core.domain import (
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
)
from orket.core.domain.sandbox_lifecycle import TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


class SandboxControlPlaneClosureError(ValueError):
    """Raised when sandbox closure cannot truthfully publish control-plane final truth."""


@dataclass(frozen=True)
class SandboxFinalTruthProjection:
    result_class: ResultClass
    completion_classification: CompletionClassification
    evidence_sufficiency_classification: EvidenceSufficiencyClassification
    residual_uncertainty_classification: ResidualUncertaintyClassification
    degradation_classification: DegradationClassification
    closure_basis: ClosureBasisClassification
    authority_sources: tuple[AuthoritySourceClass, ...]


_FINAL_TRUTH_BY_TERMINAL_REASON: dict[TerminalReason, SandboxFinalTruthProjection] = {
    TerminalReason.SUCCESS: SandboxFinalTruthProjection(
        result_class=ResultClass.SUCCESS,
        completion_classification=CompletionClassification.SATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.FAILED: SandboxFinalTruthProjection(
        result_class=ResultClass.FAILED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.BLOCKED: SandboxFinalTruthProjection(
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.CANCELED: SandboxFinalTruthProjection(
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.CANCELLED_BY_AUTHORITY,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.CREATE_FAILED: SandboxFinalTruthProjection(
        result_class=ResultClass.FAILED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.START_FAILED: SandboxFinalTruthProjection(
        result_class=ResultClass.FAILED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.RESTART_LOOP: SandboxFinalTruthProjection(
        result_class=ResultClass.FAILED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP,
        authority_sources=(
            AuthoritySourceClass.RECEIPT_EVIDENCE,
            AuthoritySourceClass.ADAPTER_OBSERVATION,
        ),
    ),
    TerminalReason.LEASE_EXPIRED: SandboxFinalTruthProjection(
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
    TerminalReason.HARD_MAX_AGE: SandboxFinalTruthProjection(
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP,
        authority_sources=(AuthoritySourceClass.RECEIPT_EVIDENCE,),
    ),
}


class SandboxControlPlaneClosureService:
    """Maps sandbox terminal outcomes into first-class control-plane closure records."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_terminal_final_truth(
        self,
        *,
        record: SandboxLifecycleRecord,
        reconciliation_record: ReconciliationRecord | None = None,
    ) -> FinalTruthRecord:
        if record.run_id is None:
            raise SandboxControlPlaneClosureError("sandbox control-plane final truth requires run_id")
        if record.terminal_reason is None:
            raise SandboxControlPlaneClosureError("sandbox control-plane final truth requires terminal_reason")
        authoritative_result_ref = record.required_evidence_ref
        if record.terminal_reason is TerminalReason.LOST_RUNTIME:
            if reconciliation_record is None:
                raise SandboxControlPlaneClosureError(
                    "lost_runtime control-plane final truth requires reconciliation_record"
                )
            authoritative_result_ref = reconciliation_record.reconciliation_id
        elif record.required_evidence_ref is None:
            raise SandboxControlPlaneClosureError("sandbox control-plane final truth requires required_evidence_ref")
        projection = self._projection_for_terminal_reason(
            record.terminal_reason,
            reconciliation_record=reconciliation_record,
        )
        return await self.publication.publish_final_truth(
            final_truth_record_id=self._final_truth_record_id(record),
            run_id=record.run_id,
            result_class=projection.result_class,
            completion_classification=projection.completion_classification,
            evidence_sufficiency_classification=projection.evidence_sufficiency_classification,
            residual_uncertainty_classification=projection.residual_uncertainty_classification,
            degradation_classification=projection.degradation_classification,
            closure_basis=projection.closure_basis,
            authority_sources=list(projection.authority_sources),
            authoritative_result_ref=authoritative_result_ref,
        )

    @staticmethod
    def _final_truth_record_id(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-final-truth:{record.run_id}:{record.record_version:08d}"

    @staticmethod
    def _projection_for_terminal_reason(
        reason: TerminalReason,
        *,
        reconciliation_record: ReconciliationRecord | None = None,
    ) -> SandboxFinalTruthProjection:
        if reason is TerminalReason.LOST_RUNTIME:
            if reconciliation_record is None:
                raise SandboxControlPlaneClosureError(
                    "lost_runtime control-plane final truth requires reconciliation_record"
                )
            return SandboxFinalTruthProjection(
                result_class=ResultClass.BLOCKED,
                completion_classification=CompletionClassification.UNSATISFIED,
                evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
                residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
                degradation_classification=DegradationClassification.NONE,
                closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
                authority_sources=(
                    AuthoritySourceClass.RECONCILIATION_RECORD,
                    AuthoritySourceClass.ADAPTER_OBSERVATION,
                ),
            )
        projection = _FINAL_TRUTH_BY_TERMINAL_REASON.get(reason)
        if projection is None:
            raise SandboxControlPlaneClosureError(
                f"unsupported sandbox terminal_reason for control-plane closure: {reason.value}"
            )
        return projection


__all__ = [
    "SandboxControlPlaneClosureError",
    "SandboxControlPlaneClosureService",
    "SandboxFinalTruthProjection",
]
