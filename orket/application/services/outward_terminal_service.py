"""One outward terminal publisher using the shared final-truth authority."""

from __future__ import annotations

from dataclasses import replace

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.application.services.outward_control_plane_service import (
    authority_adoption_event_id,
    require_outward_authority,
)
from orket.application.services.outward_run_lifecycle import run_event, terminal_projection, terminal_transition
from orket.application.services.outward_terminal_evidence import TerminalCause, terminal_evidence_refs
from orket.core.contracts import StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    RunState,
)
from orket.core.domain.control_plane_lifecycle import validate_attempt_state_transition, validate_run_state_transition
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


async def publish_outward_terminal(
    transaction: OutwardStoreTransaction, run: OutwardRunRecord, *, at: str, outcome: str,
    reason: str | None, cause: TerminalCause, adoption: LedgerEvent | None = None,
) -> OutwardRunRecord:
    record, attempt = await require_outward_authority(transaction, run)
    references = await terminal_evidence_refs(transaction, run, outcome=outcome, cause=cause)
    success = outcome == "success"
    status, result = terminal_projection(outcome)
    next_run = RunState.COMPLETED if success else RunState.FAILED_TERMINAL
    next_attempt = AttemptState.COMPLETED if success else AttemptState.FAILED
    validate_run_state_transition(current_state=record.lifecycle_state, next_state=next_run)
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=next_attempt)
    cp = transaction.control_plane
    if await cp.records.get_final_truth(run_id=run.run_id) is not None:
        raise RuntimeError("E_OUTWARD_FINAL_TRUTH_ALREADY_PUBLISHED")
    step_id = f"outward-terminal:{attempt.attempt_id}"
    if await cp.execution.get_step_record(step_id=step_id) is not None:
        raise RuntimeError("E_OUTWARD_TERMINAL_STEP_CONFLICT")
    truth = await ControlPlanePublicationService(repository=cp.records).publish_final_truth(
        final_truth_record_id=f"outward-final-truth:{run.run_id}", run_id=run.run_id, result_class=result,
        completion_classification=CompletionClassification.SATISFIED if success else CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED if outcome == "failed"
            else ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION if success else ClosureBasisClassification.POLICY_TERMINAL_STOP,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE], authoritative_result_ref=step_id,
    )
    # A denied approval triggers the runtime's stop policy; it is not a MARK_TERMINAL operator command.
    terminal, event = await _terminal_projection(transaction, run, at, status, reason, outcome, adoption)
    event = replace(event, payload={**event.payload, "result": truth.result_class.value,
                                    "final_truth_record_id": truth.final_truth_record_id,
                                    "final_truth_digest": snapshot_digest(truth.model_dump(mode="json"))})
    if await transaction.get_event(event.event_id) is not None:
        raise RuntimeError("E_OUTWARD_TERMINAL_EVENT_CONFLICT")
    await cp.execution.save_step_record(record=StepRecord(
        step_id=step_id, attempt_id=attempt.attempt_id, step_kind="outward_terminal", namespace_scope=run.namespace,
        input_ref=record.configuration_snapshot_id, output_ref=event.event_id, receipt_refs=references,
        observed_result_classification=truth.result_class.value, closure_classification=outcome,
    ))
    attempt = await cp.execution.save_attempt_record(record=attempt.model_copy(update={"attempt_state": next_attempt, "end_timestamp": terminal.completed_at}))
    record = await cp.execution.save_run_record(record=record.model_copy(update={"lifecycle_state": next_run, "final_truth_record_id": truth.final_truth_record_id}))
    if adoption is None:
        await transaction.update_run(terminal)
    await transaction.append_event(event)
    return terminal


async def _terminal_projection(transaction, run, at, status, reason, outcome, adoption):
    if adoption is None:
        return terminal_transition(run, at=at, status=status, reason=reason, outcome=outcome)
    if (adoption.event_id != authority_adoption_event_id(run.run_id)
            or await transaction.get_event(adoption.event_id) != adoption
            or run.status != status or run.completed_at is None):
        raise RuntimeError("E_OUTWARD_TERMINAL_ADOPTION_CONFLICT")
    return run, run_event(
        run, event_id=f"{adoption.event_id}:final-truth", event_type="outward_final_truth_adopted", at=at,
        payload={"adoption_ref": adoption.event_id, "outcome": outcome, "status": run.status,
                 "historical_completed_at": run.completed_at},
    )
