"""Extension closeout under an explicitly borrowed control-plane transaction."""
from __future__ import annotations

from typing import TYPE_CHECKING

from orket.application.services.control_plane_closeout_evidence import read_terminal_truth, require_closeout_evidence
from orket.core.contracts import StepRecord
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
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.core.domain.control_plane_final_truth import ControlPlaneFinalTruthError

if TYPE_CHECKING:
    from orket.application.services.extension_workload_control_plane_service import ExtensionWorkloadControlPlaneService


async def finalize_extension_workload(
    owner: ExtensionWorkloadControlPlaneService, *, run_id: str, outcome: ResultClass,
    authoritative_result_ref: str, authority_sources: list[AuthoritySourceClass], prior_step_ref: str,
    failure_class: str, side_effect_observed: bool,
):
    run = await owner._require_run(run_id=run_id)
    attempt, truth = await read_terminal_truth(owner.execution_repository, owner.publication, run)
    next_run, attempt_update = _outcome(outcome, failure_class, side_effect_observed)
    step = StepRecord(
        step_id=owner.closeout_step_id_for(run_id=run_id), attempt_id=attempt.attempt_id,
        step_kind="extension_workload_closeout", namespace_scope=run.namespace_scope,
        input_ref=str(prior_step_ref or owner.start_result_ref_for(run_id=run_id)), output_ref=authoritative_result_ref,
        capability_used=CapabilityClass.DETERMINISTIC_COMPUTE, resources_touched=[],
        observed_result_classification=owner._closeout_observed_result(outcome),
        receipt_refs=[authoritative_result_ref], closure_classification="step_completed",
    )
    truth_args = _truth_arguments(owner, run_id, outcome, authority_sources, authoritative_result_ref)
    if truth is not None:
        if run.lifecycle_state != next_run or any(getattr(attempt, k) != v for k, v in attempt_update.items()):
            raise ControlPlaneFinalTruthError("E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:extension_outcome")
        step, effect = await require_closeout_evidence(
            owner.execution_repository, owner.publication, run=run, expected_step=step, truth=truth,
            expected_truth=owner.publication.authority.publish_final_truth(**truth_args),
            journal_entry_id=owner.journal_entry_id_for(run_id=run_id, stage="closeout"),
            effect_id=owner.effect_id_for(run_id=run_id, stage="closeout"),
            target_ref=f"extension-workload:{run_id}:closeout",
        )
        return run, attempt, step, effect, truth
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=attempt_update["attempt_state"])
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_run)
    step = await owner.execution_repository.save_step_record(record=step)
    effect = await owner._append_effect(
        run=run, attempt=attempt, step=step, effect_id=owner.effect_id_for(run_id=run_id, stage="closeout"),
        journal_entry_id=owner.journal_entry_id_for(run_id=run_id, stage="closeout"),
        intended_target_ref=f"extension-workload:{run_id}:closeout",
    )
    attempt_update["end_timestamp"] = owner._utc_now()
    attempt = await owner.execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
    truth = await owner.publication.publish_final_truth(**truth_args)
    run = await owner.execution_repository.save_run_record(record=run.model_copy(update={
        "lifecycle_state": next_run, "final_truth_record_id": truth.final_truth_record_id,
    }))
    return run, attempt, step, effect, truth


def _outcome(outcome: ResultClass, failure_class: str, side_effect_observed: bool):
    if outcome is ResultClass.SUCCESS:
        return RunState.COMPLETED, {"attempt_state": AttemptState.COMPLETED}
    if outcome not in {ResultClass.BLOCKED, ResultClass.FAILED}:
        raise ValueError(f"unsupported extension closeout outcome: {outcome}")
    return RunState.FAILED_TERMINAL, {
        "attempt_state": AttemptState.INTERRUPTED if outcome is ResultClass.BLOCKED else AttemptState.FAILED,
        "failure_class": str(failure_class or outcome.value),
        "side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED
        if side_effect_observed else SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
    }


def _truth_arguments(owner, run_id, outcome, authority_sources, result_ref):
    return dict(
        final_truth_record_id=owner.final_truth_id_for(run_id=run_id), run_id=run_id, result_class=outcome,
        completion_classification=CompletionClassification.SATISFIED if outcome is ResultClass.SUCCESS
        else CompletionClassification.UNSATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.POLICY_TERMINAL_STOP if outcome is ResultClass.BLOCKED
        else ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=authority_sources, authoritative_result_ref=result_ref,
    )
