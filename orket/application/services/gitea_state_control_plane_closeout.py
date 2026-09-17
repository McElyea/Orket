"""Gitea terminal publication inside the caller's control-plane transaction."""
from __future__ import annotations

from orket.application.services.control_plane_resource_authority_checks import require_resource_snapshot_matches_lease
from orket.core.contracts import StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.core.domain.control_plane_final_truth import validate_terminal_record_consistency


async def publish_gitea_closeout(
    service, leases, *, run_id, attempt_id, card_id, final_state, error, success_state,
    worker_id, lease_observation, lease_expired,
):
    run = await service._require_run(run_id=run_id)
    attempt = await service._require_attempt(attempt_id=attempt_id)
    lease, resource = await _require_identity(service, leases, run, attempt, card_id, worker_id, lease_observation)
    truth = await service.publication.repository.get_final_truth(run_id=run_id)
    step = await service.execution_repository.get_step_record(step_id=service.step_id_for(run_id=run_id, stage="finalize"))
    result = _result(final_state, error, success_state)
    terminal = validate_terminal_record_consistency(run, attempt, truth)
    if terminal:
        effect = await service._require_effect(run_id=run_id, stage="finalize")
        _require_terminal_reuse(service, run, attempt, truth, step, effect, lease, resource,
                                card_id, final_state, result, lease_expired)
        return run, attempt, step, effect, truth
    existing_effect = await service._existing_effect(run_id=run_id, stage="finalize")
    if step is not None or existing_effect is not None or lease.status is not LeaseStatus.ACTIVE:
        raise ValueError("E_GITEA_CLOSEOUT_PARTIAL_AUTHORITY")
    step = await _publish_step(service, run, attempt, card_id, final_state)
    effect = await service._ensure_effect(run=run, attempt=attempt, step=step, stage="finalize", card_id=card_id)
    attempt = await _close_attempt(service, run, attempt, effect, error, result)
    target_run = RunState.COMPLETED if result is ResultClass.SUCCESS else RunState.FAILED_TERMINAL
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=target_run)
    truth = await service.publication.publish_final_truth(
        final_truth_record_id=f"gitea-state-final-truth:{run.run_id}", run_id=run.run_id, result_class=result,
        completion_classification=(CompletionClassification.SATISFIED if result is ResultClass.SUCCESS
                                   else CompletionClassification.UNSATISFIED),
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=(ClosureBasisClassification.POLICY_TERMINAL_STOP if result is ResultClass.BLOCKED
                       else ClosureBasisClassification.NORMAL_EXECUTION),
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE], authoritative_result_ref=step.output_ref,
    )
    run = run.model_copy(update={"lifecycle_state": target_run, "final_truth_record_id": truth.final_truth_record_id})
    attempt = await service.execution_repository.save_attempt_record(record=attempt)
    run = await service.execution_repository.save_run_record(record=run)
    if lease_expired:
        await leases.publish_expired_lease(card_id=card_id, worker_id=worker_id,
                                          lease_observation=lease_observation, reason=error or "E_LEASE_EXPIRED")
    else:
        await leases.publish_released_lease(card_id=card_id, worker_id=worker_id,
                                           lease_observation=lease_observation, final_state=final_state)
    validate_terminal_record_consistency(run, attempt, truth)
    return run, attempt, step, effect, truth


async def _require_identity(service, leases, run, attempt, card_id, worker_id, observation):
    epoch = leases._lease_epoch(observation)
    namespace = service.namespace_scope_for(card_id=card_id)
    if (run.run_id != service.run_id_for(card_id=card_id, lease_epoch=epoch)
            or run.namespace_scope != namespace or run.workload_id != service.WORKLOAD.workload_id
            or run.workload_version != service.WORKLOAD.workload_version
            or attempt.attempt_id != run.current_attempt_id or attempt.run_id != run.run_id):
        raise ValueError("E_GITEA_CLOSEOUT_EXECUTION_IDENTITY")
    lease = await service.publication.repository.get_latest_lease_record(lease_id=leases.lease_id_for(card_id))
    resource = await service.publication.repository.get_latest_resource_record(resource_id=leases.resource_id_for(card_id))
    if (lease is None or lease.resource_id != leases.resource_id_for(card_id)
            or lease.lease_epoch != epoch or lease.holder_ref != leases.holder_ref_for(worker_id)):
        raise ValueError("E_GITEA_CLOSEOUT_LEASE_IDENTITY")
    if (resource is None or resource.resource_kind != "gitea_card" or resource.namespace_scope != namespace):
        raise ValueError("E_GITEA_CLOSEOUT_RESOURCE_IDENTITY")
    return lease, resource


def _require_terminal_reuse(service, run, attempt, truth, step, effect, lease, resource,
                            card_id, final_state, result, expired):
    expected_ref = service.transition_result_ref(card_id=card_id, lease_epoch=lease.lease_epoch,
                                                from_state="in_progress", to_state=final_state)
    if (truth.result_class is not result or truth.authoritative_result_ref != expected_ref or step is None
            or step.output_ref != expected_ref or step.attempt_id != attempt.attempt_id
            or step.namespace_scope != run.namespace_scope or step.closure_classification != "step_completed"
            or effect.attempt_id != attempt.attempt_id or effect.step_id != step.step_id
            or effect.observed_result_ref != expected_ref
            or lease.status is not (LeaseStatus.EXPIRED if expired else LeaseStatus.RELEASED)):
        raise ValueError("E_GITEA_CLOSEOUT_TERMINAL_IDENTITY")
    require_resource_snapshot_matches_lease(
        resource=resource, lease=lease, expected_resource_kind="gitea_card",
        expected_namespace_scope=run.namespace_scope, error_context="Gitea terminal reuse", error_factory=ValueError,
    )


async def _publish_step(service, run, attempt, card_id, final_state):
    claim = await service.execution_repository.get_step_record(step_id=service.step_id_for(run_id=run.run_id, stage="claim"))
    output = service.transition_result_ref(card_id=card_id, lease_epoch=service.lease_epoch_for_run(run_id=run.run_id),
                                          from_state="in_progress", to_state=final_state)
    return await service.execution_repository.save_step_record(record=StepRecord(
        step_id=service.step_id_for(run_id=run.run_id, stage="finalize"), attempt_id=attempt.attempt_id,
        step_kind="gitea_state_transition", namespace_scope=run.namespace_scope,
        input_ref=claim.output_ref if claim is not None and claim.output_ref else run.admission_decision_receipt_ref,
        output_ref=output, capability_used=CapabilityClass.EXTERNAL_MUTATION,
        resources_touched=service._resources_touched(card_id=card_id),
        observed_result_classification="state_transition_succeeded", receipt_refs=[output],
        closure_classification="step_completed",
    ))


def _result(final_state, error, success_state):
    if not error and final_state == str(success_state).strip():
        return ResultClass.SUCCESS
    if str(error or "").strip().upper() in {"E_LEASE_EXPIRED", "E_CONTROL_PLANE_RESOURCE_DRIFT"}:
        return ResultClass.BLOCKED
    return ResultClass.FAILED


async def _close_attempt(service, run, attempt, effect, error, result):
    target = (AttemptState.COMPLETED if result is ResultClass.SUCCESS else
              AttemptState.INTERRUPTED if result is ResultClass.BLOCKED else AttemptState.FAILED)
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=target)
    attempt = attempt.model_copy(update={"attempt_state": target, "end_timestamp": service.now_utc()})
    if result is ResultClass.SUCCESS:
        return attempt
    failure = {"E_LEASE_EXPIRED": "lease_expired", "E_CONTROL_PLANE_RESOURCE_DRIFT": "control_plane_resource_drift"}.get(
        str(error or "").strip().upper(), "gitea_state_worker_failure",
    )
    decision = await service.publication.publish_recovery_decision(
        decision_id=f"gitea-state-recovery:{run.run_id}:{failure}", run_id=run.run_id,
        failed_attempt_id=attempt.attempt_id, failure_classification_basis=failure,
        side_effect_boundary_class=SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
        recovery_policy_ref="gitea_state_worker_terminal_policy.v1",
        authorized_next_action=RecoveryActionClass.TERMINATE_RUN, rationale_ref=effect.journal_entry_id,
    )
    return attempt.model_copy(update={"side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
        "failure_class": failure, "recovery_decision_id": decision.decision_id,
        "failure_plane": decision.failure_plane, "failure_classification": decision.failure_classification})
