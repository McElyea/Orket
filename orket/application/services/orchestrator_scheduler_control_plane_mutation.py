from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots
from orket.application.services.orchestrator_issue_control_plane_support import (
    attempt_id_for_run,
    classify_terminal_recovery_failure,
    digest,
    lease_id_for_run,
    namespace_resource_id,
    namespace_scope,
    utc_now,
)
from orket.core.contracts import AttemptRecord, LeaseRecord, ReservationRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
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
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


async def create_namespace_execution(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run_id: str,
    workload_id: str,
    workload_version: str,
    issue_id: str,
    admission_ref: str,
    policy_payload: dict[str, object],
    config_payload: dict[str, object],
    created_at: str,
) -> tuple[RunRecord, AttemptRecord]:
    attempt_id = attempt_id_for_run(run_id=run_id)
    run = RunRecord(
        run_id=run_id,
        workload_id=workload_id,
        workload_version=workload_version,
        policy_snapshot_id=f"{workload_id}-policy:{run_id}",
        policy_digest=digest(policy_payload),
        configuration_snapshot_id=f"{workload_id}-config:{run_id}",
        configuration_digest=digest(config_payload),
        creation_timestamp=created_at,
        admission_decision_receipt_ref=admission_ref,
        namespace_scope=namespace_scope(issue_id=issue_id),
        lifecycle_state=RunState.ADMISSION_PENDING,
        current_attempt_id=attempt_id,
    )
    await publish_run_snapshots(
        publication=publication,
        run=run,
        policy_payload=policy_payload,
        policy_source_refs=[admission_ref],
        configuration_payload=config_payload,
        configuration_source_refs=[admission_ref],
    )
    attempt = AttemptRecord(
        attempt_id=attempt_id,
        run_id=run_id,
        attempt_ordinal=1,
        attempt_state=AttemptState.CREATED,
        starting_state_snapshot_ref=admission_ref,
        start_timestamp=created_at,
    )
    await execution_repository.save_run_record(record=run)
    await execution_repository.save_attempt_record(record=attempt)
    return run, attempt


async def activate_namespace_authority(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    promotion_rule: str,
    cleanup_rule: str,
    run: RunRecord,
    attempt: AttemptRecord,
    workload_id: str,
    holder_ref: str,
    issue_id: str,
    step_kind: str,
    created_at: str,
) -> tuple[RunRecord, AttemptRecord, ReservationRecord, LeaseRecord]:
    reservation = await publication.publish_reservation(
        reservation_id=f"{workload_id}-reservation:{run.run_id}",
        holder_ref=holder_ref,
        reservation_kind=ReservationKind.NAMESPACE,
        target_scope_ref=namespace_resource_id(issue_id=issue_id),
        creation_timestamp=created_at,
        expiry_or_invalidation_basis=f"{step_kind}_reserved",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"{workload_id}-supervisor:{run.run_id}:reserve_namespace",
        promotion_rule=promotion_rule,
    )
    try:
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.ADMITTED)
        run = run.model_copy(update={"lifecycle_state": RunState.ADMITTED})
        await execution_repository.save_run_record(record=run)
        lease = await publication.publish_lease(
            lease_id=lease_id_for_run(run_id=run.run_id),
            resource_id=namespace_resource_id(issue_id=issue_id),
            holder_ref=holder_ref,
            lease_epoch=1,
            publication_timestamp=created_at,
            expiry_basis=f"{step_kind}_active",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule=cleanup_rule,
            source_reservation_id=reservation.reservation_id,
        )
        await publication.promote_reservation_to_lease(
            reservation_id=reservation.reservation_id,
            promoted_lease_id=lease.lease_id,
            supervisor_authority_ref=f"{workload_id}-supervisor:{run.run_id}:promote_namespace_lease",
            promotion_basis=f"{step_kind}_started",
        )
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
        active_run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
        active_attempt = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
        await execution_repository.save_run_record(record=active_run)
        await execution_repository.save_attempt_record(record=active_attempt)
        return active_run, active_attempt, reservation, lease
    except Exception:
        await _rollback_namespace_authority_activation(
            publication=publication,
            workload_id=workload_id,
            run_id=run.run_id,
            reservation_id=reservation.reservation_id,
            step_kind=step_kind,
        )
        raise


async def _rollback_namespace_authority_activation(
    *,
    publication: ControlPlanePublicationService,
    workload_id: str,
    run_id: str,
    reservation_id: str,
    step_kind: str,
) -> None:
    failed_at = utc_now()
    lease = await publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    if lease is not None and lease.status is LeaseStatus.ACTIVE:
        await publication.publish_lease(
            lease_id=lease.lease_id,
            resource_id=lease.resource_id,
            holder_ref=lease.holder_ref,
            lease_epoch=lease.lease_epoch,
            publication_timestamp=failed_at,
            expiry_basis=f"{step_kind}_activation_failed",
            status=LeaseStatus.RELEASED,
            cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
            last_confirmed_observation=lease.last_confirmed_observation,
            source_reservation_id=lease.source_reservation_id,
        )
    reservation = await publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
    if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
        await publication.invalidate_reservation(
            reservation_id=reservation_id,
            supervisor_authority_ref=f"{workload_id}-supervisor:{run_id}:activation_fail_closeout",
            invalidation_basis=f"{step_kind}_activation_failed",
        )


async def publish_mutation_step_and_effect(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    workload_id: str,
    admission_ref: str,
    attempt_id: str,
    step_kind: str,
    input_ref: str,
    output_ref: str,
    capability_used: CapabilityClass,
    resources: list[str],
    observed_result_classification: str,
    intended_target_ref: str,
    created_at: str,
) -> StepRecord:
    step = await execution_repository.save_step_record(
        record=StepRecord(
            step_id=f"{run.run_id}:step:mutate",
            attempt_id=attempt_id,
            step_kind=step_kind,
            namespace_scope=run.namespace_scope,
            input_ref=input_ref,
            output_ref=output_ref,
            capability_used=capability_used,
            resources_touched=resources,
            observed_result_classification=observed_result_classification,
            receipt_refs=[output_ref],
            closure_classification="step_completed",
        )
    )
    await publication.append_effect_journal_entry(
        journal_entry_id=f"{workload_id}-journal:{run.run_id}:mutate",
        effect_id=f"{workload_id}-effect:{run.run_id}:mutate",
        run_id=run.run_id,
        attempt_id=attempt_id,
        step_id=step.step_id,
        authorization_basis_ref=admission_ref,
        publication_timestamp=created_at,
        intended_target_ref=intended_target_ref,
        observed_result_ref=output_ref,
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref=output_ref,
    )
    return step


async def close_namespace_mutation(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    attempt: AttemptRecord,
    lease,
    workload_id: str,
    step_kind: str,
    output_ref: str,
    result_class: ResultClass,
    completion_classification: CompletionClassification,
    closure_basis: ClosureBasisClassification,
    ended_at: str,
) -> None:
    attempt_state = _attempt_state_for(result_class)
    run_state = _run_state_for(result_class)
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=attempt_state)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=run_state)
    attempt_update: dict[str, object] = {"attempt_state": attempt_state, "end_timestamp": ended_at}
    if attempt_state is AttemptState.FAILED:
        failure_basis, failure_plane, failure_classification, boundary = classify_terminal_recovery_failure(
            result_class=result_class,
            closure_basis=closure_basis,
            reason=step_kind,
        )
        decision = await publication.publish_recovery_decision(
            decision_id=f"{workload_id}-recovery:{run.run_id}:closeout",
            run_id=run.run_id,
            failed_attempt_id=attempt.attempt_id,
            failure_classification_basis=failure_basis,
            failure_plane=failure_plane,
            failure_classification=failure_classification,
            side_effect_boundary_class=boundary,
            recovery_policy_ref=run.policy_snapshot_id,
            authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
            rationale_ref=output_ref,
        )
        attempt_update.update(
            {
                "side_effect_boundary_class": boundary,
                "failure_class": failure_basis,
                "failure_plane": decision.failure_plane,
                "failure_classification": decision.failure_classification,
                "recovery_decision_id": decision.decision_id,
            }
        )
    truth = await publication.publish_final_truth(
        final_truth_record_id=f"{workload_id}-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=result_class,
        completion_classification=completion_classification,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=closure_basis,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref=output_ref,
    )
    await execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
    await execution_repository.save_run_record(
        record=run.model_copy(update={"lifecycle_state": run_state, "final_truth_record_id": truth.final_truth_record_id})
    )
    await publication.publish_lease(
        lease_id=lease.lease_id,
        resource_id=lease.resource_id,
        holder_ref=lease.holder_ref,
        lease_epoch=lease.lease_epoch,
        publication_timestamp=ended_at,
        expiry_basis=f"{step_kind}_closed",
        status=LeaseStatus.RELEASED,
        cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
        last_confirmed_observation=output_ref,
        source_reservation_id=lease.source_reservation_id,
    )


def _attempt_state_for(result_class: ResultClass) -> AttemptState:
    if result_class is ResultClass.SUCCESS:
        return AttemptState.COMPLETED
    return AttemptState.FAILED


def _run_state_for(result_class: ResultClass) -> RunState:
    if result_class is ResultClass.SUCCESS:
        return RunState.COMPLETED
    return RunState.FAILED_TERMINAL


__all__ = [
    "activate_namespace_authority",
    "close_namespace_mutation",
    "create_namespace_execution",
    "publish_mutation_step_and_effect",
]
