from __future__ import annotations

from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    OperatorInputClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    TerminalityBasisClassification,
)
from orket.core.domain.control_plane_lifecycle import is_terminal_attempt_state, is_terminal_run_state

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import (
        AttemptRecord,
        FinalTruthRecord,
        OperatorActionRecord,
        RunRecord,
    )


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


def validate_terminal_record_consistency(
    run: RunRecord, attempt: AttemptRecord | None, truth: FinalTruthRecord | None,
) -> bool:
    """Validate the common terminal join; active recovery may retain a closed attempt."""
    terminal = is_terminal_run_state(run.lifecycle_state)
    if not terminal and run.final_truth_record_id is None and truth is None:
        return False
    if (not terminal or truth is None or truth.run_id != run.run_id
            or truth.final_truth_record_id != run.final_truth_record_id):
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:run_truth")
    if (attempt is None or attempt.attempt_id != run.current_attempt_id or attempt.run_id != run.run_id
            or not is_terminal_attempt_state(attempt.attempt_state) or attempt.end_timestamp is None):
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:attempt")
    complete = run.lifecycle_state is RunState.COMPLETED
    if complete != (truth.result_class is ResultClass.SUCCESS) or complete != (attempt.attempt_state is AttemptState.COMPLETED):
        raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:result")
    return True


def build_final_truth_record(
    *,
    final_truth_record_id: str,
    run_id: str,
    result_class: ResultClass,
    completion_classification: CompletionClassification,
    evidence_sufficiency_classification: EvidenceSufficiencyClassification,
    residual_uncertainty_classification: ResidualUncertaintyClassification,
    degradation_classification: DegradationClassification,
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
    "validate_terminal_record_consistency",
]
