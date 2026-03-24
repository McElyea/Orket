# Layer: contract

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.contracts import FinalTruthRecord, OperatorActionRecord
from orket.core.domain import (
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    ControlPlaneFinalTruthError,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    OperatorCommandClass,
    OperatorInputClass,
    ResidualUncertaintyClassification,
    ResultClass,
    TerminalityBasisClassification,
    build_final_truth_record,
    terminality_basis_for_closure,
    validate_final_truth_publication,
)


pytestmark = pytest.mark.contract


def _mark_terminal_action() -> OperatorActionRecord:
    return OperatorActionRecord(
        action_id="op-1",
        actor_ref="operator-1",
        input_class=OperatorInputClass.COMMAND,
        target_ref="run-1",
        timestamp="2026-03-23T00:20:00+00:00",
        precondition_basis_ref="recon-1",
        result="accepted",
        command_class=OperatorCommandClass.MARK_TERMINAL,
    )


@pytest.mark.parametrize(
    ("closure_basis", "expected_terminality"),
    [
        (ClosureBasisClassification.NORMAL_EXECUTION, TerminalityBasisClassification.COMPLETED_TERMINAL),
        (ClosureBasisClassification.RECONCILIATION_CLOSED, TerminalityBasisClassification.COMPLETED_TERMINAL),
        (ClosureBasisClassification.POLICY_TERMINAL_STOP, TerminalityBasisClassification.POLICY_TERMINAL),
        (ClosureBasisClassification.OPERATOR_TERMINAL_STOP, TerminalityBasisClassification.OPERATOR_TERMINAL),
        (ClosureBasisClassification.CANCELLED_BY_AUTHORITY, TerminalityBasisClassification.CANCELLED_TERMINAL),
    ],
)
def test_terminality_basis_for_closure_matches_authority(
    closure_basis: ClosureBasisClassification,
    expected_terminality: TerminalityBasisClassification,
) -> None:
    assert terminality_basis_for_closure(closure_basis) is expected_terminality


def test_final_truth_record_rejects_reconciliation_closure_without_reconciliation_authority() -> None:
    with pytest.raises(ValidationError, match="reconciliation_closed requires reconciliation_record authority source"):
        FinalTruthRecord(
            final_truth_record_id="truth-3",
            run_id="run-3",
            result_class=ResultClass.DEGRADED,
            completion_classification=CompletionClassification.PARTIAL,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
            degradation_classification=DegradationClassification.DECLARED,
            closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
            terminality_basis=TerminalityBasisClassification.COMPLETED_TERMINAL,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        )


def test_build_final_truth_record_derives_operator_terminality() -> None:
    record = build_final_truth_record(
        final_truth_record_id="truth-4",
        run_id="run-4",
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.OPERATOR_TERMINAL_STOP,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        operator_action=_mark_terminal_action(),
    )

    assert record.terminality_basis is TerminalityBasisClassification.OPERATOR_TERMINAL


def test_validate_final_truth_publication_rejects_non_command_operator_terminal_closure() -> None:
    record = FinalTruthRecord(
        final_truth_record_id="truth-5",
        run_id="run-5",
        result_class=ResultClass.BLOCKED,
        completion_classification=CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.INSUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.OPERATOR_TERMINAL_STOP,
        terminality_basis=TerminalityBasisClassification.OPERATOR_TERMINAL,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
    )
    risk_acceptance = OperatorActionRecord(
        action_id="op-2",
        actor_ref="operator-1",
        input_class=OperatorInputClass.RISK_ACCEPTANCE,
        target_ref="run-5",
        timestamp="2026-03-23T00:21:00+00:00",
        precondition_basis_ref="recon-2",
        result="accepted",
        risk_acceptance_scope="bounded uncertainty",
    )

    with pytest.raises(ControlPlaneFinalTruthError, match="operator command input"):
        validate_final_truth_publication(record, operator_action=risk_acceptance)
