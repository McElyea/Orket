"""Issue-dispatch terminal publication over borrowed transaction repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING

from orket.application.services.orchestrator_issue_control_plane_support import (
    classify_closeout,
    classify_terminal_recovery_failure,
    holder_ref_for_issue,
    lease_id_for_run,
    namespace_scope,
    observation_ref,
    resources_touched,
    run_id_from_reservation_id,
    status_ref,
    status_token,
    transition_ref,
)
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    RecoveryActionClass,
    ReservationStatus,
    ResidualUncertaintyClassification,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.schema import CardStatus

if TYPE_CHECKING:
    from orket.application.services.orchestrator_issue_control_plane_service import OrchestratorIssueControlPlaneService


async def _active_records(
    owner: OrchestratorIssueControlPlaneService,
    session_id: str,
    issue_id: str,
    error_type: type[Exception],
) -> tuple[RunRecord, AttemptRecord] | None:
    latest = await owner.publication.repository.get_latest_reservation_record_for_holder_ref(
        holder_ref=holder_ref_for_issue(session_id=session_id, issue_id=issue_id)
    )
    if latest is None or latest.status is not ReservationStatus.PROMOTED_TO_LEASE:
        return None
    run_id = run_id_from_reservation_id(reservation_id=latest.reservation_id)
    run = await owner.execution_repository.get_run_record(run_id=run_id)
    if run is None:
        return None
    if run.final_truth_record_id is not None:
        await owner._require_closed_existing_dispatch_run(
            run_id=run_id, expected_namespace_scope=namespace_scope(issue_id=issue_id)
        )
        return None
    await owner._require_active_dispatch_resource_authority(run=run)
    current_attempt_id = str(run.current_attempt_id or "").strip()
    if not current_attempt_id:
        raise error_type(f"orchestrator issue dispatch active run missing current attempt id: {run_id}")
    attempt = await owner.execution_repository.get_attempt_record(attempt_id=current_attempt_id)
    if attempt is None:
        raise error_type(f"orchestrator issue dispatch missing attempt: {run_id}")
    owner._require_active_dispatch_run_attempt(
        run=run, attempt=attempt, expected_namespace_scope=namespace_scope(issue_id=issue_id)
    )
    return run, attempt


async def close_active_dispatch(
    owner: OrchestratorIssueControlPlaneService,
    *,
    session_id: str,
    issue_id: str,
    current_status: CardStatus | str,
    target_status: CardStatus | str,
    reason: str,
    observation_only: bool,
    ended_at: str,
    error_type: type[Exception],
) -> bool:
    active = await _active_records(owner, session_id, issue_id, error_type)
    if active is None:
        return False
    run, attempt = active
    closeout_ref = (
        observation_ref(session_id=session_id, issue_id=issue_id, status=target_status, reason=reason)
        if observation_only
        else transition_ref(
            session_id=session_id, issue_id=issue_id, from_status=current_status, to_status=target_status, reason=reason
        )
    )
    step = await owner.execution_repository.save_step_record(
        record=StepRecord(
            step_id=f"{run.run_id}:step:closeout",
            attempt_id=attempt.attempt_id,
            step_kind="issue_status_observation" if observation_only else "issue_status_transition",
            namespace_scope=run.namespace_scope,
            input_ref=status_ref(session_id=session_id, issue_id=issue_id, status=current_status),
            output_ref=closeout_ref,
            capability_used=CapabilityClass.OBSERVE if observation_only else CapabilityClass.BOUNDED_LOCAL_MUTATION,
            resources_touched=resources_touched(issue_id=issue_id),
            observed_result_classification=(
                f"issue_dispatch_observed:{status_token(target_status)}"
                if observation_only
                else f"issue_dispatch_closeout:{status_token(target_status)}"
            ),
            receipt_refs=[closeout_ref],
            closure_classification="step_completed",
        )
    )
    await _append_closeout_effect(owner, run, attempt, step, issue_id, ended_at)
    run = await _publish_terminal(owner, run, attempt, target_status, reason, closeout_ref, ended_at)
    await _release_lease(owner, run, reason, ended_at)
    return True


async def _append_closeout_effect(
    owner: OrchestratorIssueControlPlaneService,
    run: RunRecord,
    attempt: AttemptRecord,
    step: StepRecord,
    issue_id: str,
    ended_at: str,
) -> None:
    existing = await owner.publication.repository.list_effect_journal_entries(run_id=run.run_id)
    if any(entry.step_id == step.step_id for entry in existing):
        return
    await owner.publication.append_effect_journal_entry(
        journal_entry_id=f"orchestrator-issue-journal:{run.run_id}:closeout",
        effect_id=f"orchestrator-issue-effect:{run.run_id}:closeout",
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        step_id=step.step_id,
        authorization_basis_ref=step.output_ref or step.input_ref,
        publication_timestamp=ended_at,
        intended_target_ref=f"issue:{issue_id}",
        observed_result_ref=step.output_ref,
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref=step.output_ref or step.input_ref,
    )


async def _publish_terminal(
    owner: OrchestratorIssueControlPlaneService,
    run: RunRecord,
    attempt: AttemptRecord,
    target_status: CardStatus | str,
    reason: str,
    closeout_ref: str,
    ended_at: str,
) -> RunRecord:
    attempt_state, run_state, result_class, completion_classification, closure_basis = classify_closeout(
        target_status=target_status, reason=reason
    )
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=attempt_state)
    validate_run_state_transition(current_state=run.lifecycle_state, next_state=run_state)
    attempt_update: dict[str, object] = {"attempt_state": attempt_state, "end_timestamp": ended_at}
    if attempt_state is AttemptState.FAILED:
        failure_basis, failure_plane, failure_classification, boundary = classify_terminal_recovery_failure(
            result_class=result_class, closure_basis=closure_basis, reason=reason
        )
        decision = await owner.publication.publish_recovery_decision(
            decision_id=f"orchestrator-issue-recovery:{run.run_id}:{reason}",
            run_id=run.run_id,
            failed_attempt_id=attempt.attempt_id,
            failure_classification_basis=failure_basis,
            failure_plane=failure_plane,
            failure_classification=failure_classification,
            side_effect_boundary_class=boundary,
            recovery_policy_ref=run.policy_snapshot_id,
            authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
            rationale_ref=closeout_ref,
        )
        attempt_update.update(
            side_effect_boundary_class=boundary,
            failure_class=failure_basis,
            failure_plane=decision.failure_plane,
            failure_classification=decision.failure_classification,
            recovery_decision_id=decision.decision_id,
        )
    truth = await owner.publication.publish_final_truth(
        final_truth_record_id=f"orchestrator-issue-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=result_class,
        completion_classification=completion_classification,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=closure_basis,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref=closeout_ref,
    )
    await owner.execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
    return await owner.execution_repository.save_run_record(
        record=run.model_copy(
            update={"lifecycle_state": run_state, "final_truth_record_id": truth.final_truth_record_id}
        )
    )


async def _release_lease(
    owner: OrchestratorIssueControlPlaneService,
    run: RunRecord,
    reason: str,
    ended_at: str,
) -> None:
    lease = await owner.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    if lease is not None and lease.status is LeaseStatus.ACTIVE:
        released = await owner.publication.publish_lease(
            lease_id=lease.lease_id,
            resource_id=lease.resource_id,
            holder_ref=lease.holder_ref,
            lease_epoch=lease.lease_epoch,
            publication_timestamp=ended_at,
            expiry_basis=f"issue_dispatch_closed:{reason}",
            status=LeaseStatus.RELEASED,
            cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
            last_confirmed_observation=lease.last_confirmed_observation,
            source_reservation_id=lease.source_reservation_id,
        )
        await owner._publish_resource_snapshot(run=run, lease=released)
