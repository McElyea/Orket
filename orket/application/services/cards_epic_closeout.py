"""Close out a cards epic using the caller's explicit control-plane transaction."""
from __future__ import annotations

from typing import Any

from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.core.domain.control_plane_final_truth import (
    ControlPlaneFinalTruthError,
    validate_terminal_record_consistency,
)


async def finalize_cards_epic_closeout(
    owner: Any, *, run_id: str, session_status: str, failure_reason: str | None, error_type: type[ValueError],
) -> tuple[RunRecord, AttemptRecord]:
    run = await owner._require_run(run_id=run_id)
    attempt = await owner._require_attempt(attempt_id=run.current_attempt_id)
    try:
        truth = await owner.publication.repository.get_final_truth(run_id=run_id)
        validate_terminal_record_consistency(run, attempt, truth)
    except ControlPlaneFinalTruthError as exc:
        raise error_type("E_CARDS_EPIC_CLOSEOUT_EVIDENCE_CONFLICT") from exc
    status = str(session_status or "").strip().lower()
    states = {"done": (RunState.COMPLETED, AttemptState.COMPLETED),
              "terminal_failure": (RunState.FAILED_TERMINAL, AttemptState.FAILED),
              "failed": (RunState.FAILED_TERMINAL, AttemptState.FAILED),
              "incomplete": (RunState.WAITING_ON_OBSERVATION, AttemptState.WAITING)}
    if status not in states:
        raise error_type(f"unsupported cards epic session_status={session_status!r}")
    next_run, next_attempt = states[status]
    closeout_ref = owner.closeout_ref_for(run_id=run_id, session_status=status)
    if run.lifecycle_state == next_run and attempt.attempt_state == next_attempt:
        await _require_retained_closeout(owner, run, attempt, status, closeout_ref, failure_reason, error_type)
        return run, attempt
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=next_attempt)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_run)
    attempt_update: dict[str, Any] = {"attempt_state": next_attempt}
    if status != "incomplete":
        attempt_update["end_timestamp"] = owner._utc_now()
    if next_attempt == AttemptState.FAILED:
        attempt_update["failure_class"] = str(failure_reason or status)[:200]
    attempt = await owner.execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
    terminal = next_run in {RunState.COMPLETED, RunState.FAILED_TERMINAL}
    step = await owner.execution_repository.save_step_record(record=StepRecord(
        step_id=owner.closeout_step_id_for(run_id=run_id), attempt_id=attempt.attempt_id,
        step_kind="cards_epic_session_closeout" if terminal else "cards_epic_session_wait",
        input_ref=owner.start_step_id_for(run_id=run_id), output_ref=closeout_ref,
        capability_used=CapabilityClass.DETERMINISTIC_COMPUTE, resources_touched=[],
        observed_result_classification=f"cards_epic_session_{status}", receipt_refs=[closeout_ref],
        closure_classification="step_completed",
    ))
    await owner._ensure_effect(run=run, attempt=attempt, step=step, stage="closeout" if terminal else "wait")
    run_update: dict[str, Any] = {"lifecycle_state": next_run}
    if terminal:
        truth = await _publish_truth(owner, run_id, status, closeout_ref)
        run_update["final_truth_record_id"] = truth.final_truth_record_id
    run = await owner.execution_repository.save_run_record(record=run.model_copy(update=run_update))
    return run, attempt


async def _publish_truth(owner: Any, run_id: str, status: str, closeout_ref: str):
    return await owner.publication.publish_final_truth(
        final_truth_record_id=owner.final_truth_id_for(run_id=run_id), run_id=run_id,
        result_class=ResultClass.SUCCESS if status == "done" else ResultClass.FAILED,
        completion_classification=CompletionClassification.SATISFIED if status == "done" else CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE, closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE], authoritative_result_ref=closeout_ref,
    )


async def _require_retained_closeout(
    owner: Any, run: RunRecord, attempt: AttemptRecord, status: str, closeout_ref: str, failure_reason: str | None,
    error_type: type[ValueError],
) -> None:
    step = await owner.execution_repository.get_step_record(step_id=owner.closeout_step_id_for(run_id=run.run_id))
    entries = await owner.publication.repository.list_effect_journal_entries(run_id=run.run_id)
    owner.publication.authority.validate_effect_journal_history(entries)
    stage = "wait" if status == "incomplete" else "closeout"
    if (step is None or step.output_ref != closeout_ref or step.attempt_id != attempt.attempt_id
            or step.receipt_refs != [closeout_ref]
            or not any(entry.journal_entry_id == owner.journal_entry_id_for(run_id=run.run_id, stage=stage)
                       and entry.effect_id == owner.effect_id_for(run_id=run.run_id, stage=stage)
                       and entry.run_id == run.run_id and entry.attempt_id == attempt.attempt_id
                       and entry.step_id == step.step_id and entry.observed_result_ref == closeout_ref
                       and entry.integrity_verification_ref == closeout_ref
                       and entry.authorization_basis_ref == run.admission_decision_receipt_ref for entry in entries)):
        raise error_type("E_CARDS_EPIC_CLOSEOUT_EVIDENCE_MISSING")
    if status == "incomplete":
        return
    truth = await owner.publication.repository.get_final_truth(run_id=run.run_id)
    expected_result = ResultClass.SUCCESS if status == "done" else ResultClass.FAILED
    expected_completion = CompletionClassification.SATISFIED if status == "done" else CompletionClassification.UNSATISFIED
    if (truth is None or truth.result_class != expected_result
            or truth.authoritative_result_ref != closeout_ref
            or truth.completion_classification != expected_completion
            or (expected_result == ResultClass.FAILED and attempt.failure_class != str(failure_reason or status)[:200])):
        raise error_type("E_CARDS_EPIC_CLOSEOUT_EVIDENCE_CONFLICT")
