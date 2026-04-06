from __future__ import annotations

from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import (
    AuthoritySourceClass,
    ClosureBasisClassification,
    OperatorCommandClass,
    OperatorInputClass,
    TerminalityBasisClassification,
)

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import FinalTruthRecord, OperatorActionRecord


class ControlPlaneFinalTruthError(ValueError):
    """Raised when final-truth publication exceeds closure authority."""


def terminality_basis_for_closure(
    closure_basis: ClosureBasisClassification,
) -> TerminalityBasisClassification:
    mapping = {
        ClosureBasisClassification.NORMAL_EXECUTION: TerminalityBasisClassification.COMPLETED_TERMINAL,
        ClosureBasisClassification.RECONCILIATION_CLOSED: TerminalityBasisClassification.COMPLETED_TERMINAL,
        ClosureBasisClassification.POLICY_TERMINAL_STOP: TerminalityBasisClassification.POLICY_TERMINAL,
        ClosureBasisClassification.OPERATOR_TERMINAL_STOP: TerminalityBasisClassification.OPERATOR_TERMINAL,
        ClosureBasisClassification.CANCELLED_BY_AUTHORITY: TerminalityBasisClassification.CANCELLED_TERMINAL,
    }
    return mapping[closure_basis]


def validate_final_truth_publication(
    record: FinalTruthRecord,
    *,
    operator_action: OperatorActionRecord | None = None,
) -> bool:
    expected_terminality = terminality_basis_for_closure(record.closure_basis)
    if record.terminality_basis is not expected_terminality:
        raise ControlPlaneFinalTruthError("final truth terminality_basis must match closure_basis")
    if (
        record.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
        and AuthoritySourceClass.RECONCILIATION_RECORD not in record.authority_sources
    ):
        raise ControlPlaneFinalTruthError("reconciliation_closed final truth requires reconciliation_record authority")
    if record.closure_basis is ClosureBasisClassification.OPERATOR_TERMINAL_STOP:
        if operator_action is None:
            raise ControlPlaneFinalTruthError("operator terminal closure requires operator_action")
        if operator_action.input_class is not OperatorInputClass.COMMAND:
            raise ControlPlaneFinalTruthError("operator terminal closure requires operator command input")
        if operator_action.command_class is not OperatorCommandClass.MARK_TERMINAL:
            raise ControlPlaneFinalTruthError("operator terminal closure requires mark_terminal command")
    return True


def build_final_truth_record(
    *,
    final_truth_record_id: str,
    run_id: str,
    result_class: object,
    completion_classification: object,
    evidence_sufficiency_classification: object,
    residual_uncertainty_classification: object,
    degradation_classification: object,
    closure_basis: ClosureBasisClassification,
    authority_sources: list[AuthoritySourceClass],
    authoritative_result_ref: str | None = None,
    operator_action: OperatorActionRecord | None = None,
) -> FinalTruthRecord:
    from orket.core.contracts.control_plane_models import FinalTruthRecord

    record = FinalTruthRecord(
        final_truth_record_id=final_truth_record_id,
        run_id=run_id,
        result_class=result_class,
        completion_classification=completion_classification,
        evidence_sufficiency_classification=evidence_sufficiency_classification,
        residual_uncertainty_classification=residual_uncertainty_classification,
        degradation_classification=degradation_classification,
        closure_basis=closure_basis,
        terminality_basis=terminality_basis_for_closure(closure_basis),
        authority_sources=authority_sources,
        authoritative_result_ref=authoritative_result_ref,
    )
    validate_final_truth_publication(record, operator_action=operator_action)
    return record


__all__ = [
    "ControlPlaneFinalTruthError",
    "build_final_truth_record",
    "terminality_basis_for_closure",
    "validate_final_truth_publication",
]
