"""Manual review terminal writes and retained evidence under one transaction."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from orket.application.services.control_plane_closeout_evidence import read_terminal_truth, require_closeout_evidence
from orket.core.contracts import RunRecord, StepRecord
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
from orket.core.domain.control_plane_final_truth import ControlPlaneFinalTruthError

if TYPE_CHECKING:
    from orket.application.services.review_run_control_plane_service import ReviewRunControlPlaneService


async def record_review_failure(
    owner: ReviewRunControlPlaneService, *, run_id: str, original: Exception, started: bool,
) -> None:
    """Failure boundary for a public review invocation; never replace its original error."""
    logger = logging.getLogger("orket.application.review.run_service")
    try:
        finalized = await owner.finalize_failed_if_started(
            run_id=run_id, failure_class=f"review_run_{type(original).__name__}"[:200],
        )
    except Exception as closeout_error:
        logger.error("Review failure closeout also failed: run_id=%s original_error=%s", run_id,
                     type(original).__name__, exc_info=True)
        original.add_note(f"Review failure closeout also raised {type(closeout_error).__name__}; see runtime log.")
    else:
        if started and finalized is None:
            logger.error("Review run control-plane closeout was skipped after begin_execution: run_id=%s", run_id)


async def read_review_terminal(owner: ReviewRunControlPlaneService, run: RunRecord):
    attempt, truth = await read_terminal_truth(owner.execution_repository, owner.publication, run)
    if truth is not None:
        failed = truth.result_class is ResultClass.FAILED
        ref = owner.closeout_ref_for(run_id=run.run_id, failed=failed, failure_class=attempt.failure_class or "")
        expected = owner.publication.authority.publish_final_truth(**_truth_arguments(owner, run.run_id, failed, ref))
        await require_closeout_evidence(
            owner.execution_repository, owner.publication, run=run,
            expected_step=_step(owner, run.run_id, attempt.attempt_id, failed, ref), truth=truth, expected_truth=expected,
            journal_entry_id=f"review-run-journal:{run.run_id}:closeout",
            effect_id=owner.effect_id_for(run_id=run.run_id, stage="closeout"),
            target_ref=f"review-run:{run.run_id}:lifecycle",
        )
    return attempt, truth


async def finalize_review_run(
    owner: ReviewRunControlPlaneService, *, run_id: str, failed: bool, failure_class: str,
    preserve_terminal: bool = False,
):
    run = await owner._require_run(run_id=run_id)
    attempt, truth = await read_review_terminal(owner, run)
    failure_class = str(failure_class or "review_run_failed")[:200] if failed else ""
    if truth is not None:
        if not preserve_terminal and ((truth.result_class is ResultClass.FAILED) != failed
                or (failed and attempt.failure_class != failure_class)):
            raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:review_outcome")
        return run, attempt
    next_run = RunState.FAILED_TERMINAL if failed else RunState.COMPLETED
    next_attempt = AttemptState.FAILED if failed else AttemptState.COMPLETED
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=next_attempt)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_run)
    update = {"attempt_state": next_attempt, "end_timestamp": owner._utc_now()}
    if failed:
        update["failure_class"] = failure_class
    attempt = await owner.execution_repository.save_attempt_record(record=attempt.model_copy(update=update))
    ref = owner.closeout_ref_for(run_id=run_id, failed=failed, failure_class=failure_class)
    step = await owner.execution_repository.save_step_record(record=_step(owner, run_id, attempt.attempt_id, failed, ref))
    await owner._ensure_effect(run=run, attempt=attempt, step=step, stage="closeout")
    truth = await owner.publication.publish_final_truth(**_truth_arguments(owner, run_id, failed, ref))
    run = await owner.execution_repository.save_run_record(record=run.model_copy(update={
        "lifecycle_state": next_run, "final_truth_record_id": truth.final_truth_record_id,
    }))
    return run, attempt


def _step(owner, run_id, attempt_id, failed, ref):
    return StepRecord(
        step_id=owner.closeout_step_id_for(run_id=run_id), attempt_id=attempt_id,
        step_kind="review_run_closeout", input_ref=owner.start_step_id_for(run_id=run_id), output_ref=ref,
        capability_used=CapabilityClass.DETERMINISTIC_COMPUTE, resources_touched=[],
        observed_result_classification="review_run_failed" if failed else "review_run_completed",
        receipt_refs=[ref], closure_classification="step_completed",
    )


def _truth_arguments(owner, run_id, failed, ref):
    return dict(
        final_truth_record_id=owner.final_truth_id_for(run_id=run_id), run_id=run_id,
        result_class=ResultClass.FAILED if failed else ResultClass.SUCCESS,
        completion_classification=CompletionClassification.UNSATISFIED if failed else CompletionClassification.SATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE, closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE], authoritative_result_ref=ref,
    )
