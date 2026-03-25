from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_support import (
    attempt_id_for_run,
    classify_closeout,
    digest,
    holder_ref_for_issue,
    lease_id_for_run,
    namespace_scope,
    observation_ref,
    reservation_id_for_run,
    resource_id,
    resources_touched,
    run_id_for_dispatch,
    run_id_from_reservation_id,
    status_ref,
    status_token,
    transition_ref,
    utc_now,
)
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    RunState,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.schema import CardStatus


class OrchestratorIssueControlPlaneError(ValueError):
    """Raised when orchestrator issue-dispatch control-plane truth cannot be published honestly."""


class OrchestratorIssueControlPlaneService:
    """Publishes shared issue-dispatch reservation, lease, step, effect, and closeout truth."""

    WORKLOAD_ID = "orchestrator-issue-dispatch"
    WORKLOAD_VERSION = "orchestrator.issue_dispatch.v1"
    PROMOTION_RULE = "promote_on_issue_turn_dispatch"
    CLEANUP_RULE = "release_on_issue_dispatch_closeout"

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def publish_issue_transition(
        self,
        *,
        session_id: str,
        issue_id: str,
        current_status: CardStatus | str,
        target_status: CardStatus | str,
        reason: str,
        assignee: str | None = None,
        turn_index: int | None = None,
        review_turn: bool = False,
    ) -> bool:
        normalized_session_id = str(session_id or "").strip()
        normalized_issue_id = str(issue_id or "").strip()
        normalized_reason = str(reason or "").strip().lower()
        if not normalized_session_id or not normalized_issue_id:
            return False
        if normalized_reason == "turn_dispatch":
            if turn_index is None or assignee is None:
                return False
            await self._begin_dispatch(
                session_id=normalized_session_id,
                issue_id=normalized_issue_id,
                seat_name=str(assignee).strip(),
                turn_index=int(turn_index),
                current_status=current_status,
                target_status=target_status,
                review_turn=review_turn,
            )
            return True
        return await self._close_active_dispatch(
            session_id=normalized_session_id,
            issue_id=normalized_issue_id,
            current_status=current_status,
            target_status=target_status,
            reason=normalized_reason,
        )

    async def close_from_observed_status(
        self,
        *,
        session_id: str,
        issue_id: str,
        observed_status: CardStatus | str,
        reason: str = "turn_completed_observed_status",
    ) -> None:
        await self._close_active_dispatch(
            session_id=str(session_id or "").strip(),
            issue_id=str(issue_id or "").strip(),
            current_status=observed_status,
            target_status=observed_status,
            reason=str(reason or "").strip().lower(),
            observation_only=True,
        )

    async def _begin_dispatch(
        self,
        *,
        session_id: str,
        issue_id: str,
        seat_name: str,
        turn_index: int,
        current_status: CardStatus | str,
        target_status: CardStatus | str,
        review_turn: bool,
    ) -> None:
        holder_ref = holder_ref_for_issue(session_id=session_id, issue_id=issue_id)
        latest = await self.publication.repository.get_latest_reservation_record_for_holder_ref(holder_ref=holder_ref)
        if latest is not None and latest.status is ReservationStatus.PROMOTED_TO_LEASE:
            active_run_id = run_id_from_reservation_id(reservation_id=latest.reservation_id)
            active_run = await self.execution_repository.get_run_record(run_id=active_run_id)
            if active_run is not None and active_run.final_truth_record_id is None:
                raise OrchestratorIssueControlPlaneError(
                    f"orchestrator issue dispatch already has active control-plane truth: {session_id}:{issue_id}"
                )
        run_id = run_id_for_dispatch(
            session_id=session_id,
            issue_id=issue_id,
            seat_name=seat_name,
            turn_index=turn_index,
        )
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is not None:
            return
        created_at = utc_now()
        admission_ref = transition_ref(
            session_id=session_id,
            issue_id=issue_id,
            from_status=current_status,
            to_status=target_status,
            reason="turn_dispatch",
        )
        run = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD_ID,
            workload_version=self.WORKLOAD_VERSION,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest=digest({"reason": "turn_dispatch", "review_turn": review_turn}),
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest=digest(
                {
                    "session_id": session_id,
                    "issue_id": issue_id,
                    "seat_name": seat_name,
                    "turn_index": turn_index,
                    "review_turn": review_turn,
                    "from_status": status_token(current_status),
                    "to_status": status_token(target_status),
                }
            ),
            creation_timestamp=created_at,
            admission_decision_receipt_ref=admission_ref,
            namespace_scope=namespace_scope(issue_id=issue_id),
            lifecycle_state=RunState.ADMISSION_PENDING,
            current_attempt_id=attempt_id_for_run(run_id=run_id),
        )
        attempt = AttemptRecord(
            attempt_id=attempt_id_for_run(run_id=run_id),
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.CREATED,
            starting_state_snapshot_ref=admission_ref,
            start_timestamp=created_at,
        )
        await self.execution_repository.save_run_record(record=run)
        await self.execution_repository.save_attempt_record(record=attempt)
        await self.publication.publish_reservation(
            reservation_id=reservation_id_for_run(run_id=run_id),
            holder_ref=holder_ref,
            reservation_kind=ReservationKind.CONCURRENCY,
            target_scope_ref=resource_id(session_id=session_id, issue_id=issue_id),
            creation_timestamp=created_at,
            expiry_or_invalidation_basis="issue_turn_dispatch_reserved",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:dispatch",
            promotion_rule=self.PROMOTION_RULE,
        )
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.ADMITTED)
        run = run.model_copy(update={"lifecycle_state": RunState.ADMITTED})
        await self.execution_repository.save_run_record(record=run)
        lease = await self.publication.publish_lease(
            lease_id=lease_id_for_run(run_id=run_id),
            resource_id=resource_id(session_id=session_id, issue_id=issue_id),
            holder_ref=holder_ref,
            lease_epoch=1,
            publication_timestamp=created_at,
            expiry_basis="issue_turn_dispatch_active",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule=self.CLEANUP_RULE,
            source_reservation_id=reservation_id_for_run(run_id=run_id),
        )
        await self.publication.promote_reservation_to_lease(
            reservation_id=reservation_id_for_run(run_id=run_id),
            promoted_lease_id=lease.lease_id,
            supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:promote_dispatch_lease",
            promotion_basis="issue_turn_dispatch_started",
        )
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
        await self.execution_repository.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
        await self.execution_repository.save_attempt_record(
            record=attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
        )
        step = await self.execution_repository.save_step_record(
            record=StepRecord(
                step_id=f"{run_id}:step:dispatch",
                attempt_id=attempt.attempt_id,
                step_kind="issue_status_transition",
                namespace_scope=namespace_scope(issue_id=issue_id),
                input_ref=status_ref(session_id=session_id, issue_id=issue_id, status=current_status),
                output_ref=admission_ref,
                capability_used=CapabilityClass.BOUNDED_LOCAL_MUTATION,
                resources_touched=resources_touched(issue_id=issue_id),
                observed_result_classification="issue_dispatch_transition_applied",
                receipt_refs=[admission_ref],
                closure_classification="step_completed",
            )
        )
        await self.publication.append_effect_journal_entry(
            journal_entry_id=f"orchestrator-issue-journal:{run_id}:dispatch",
            effect_id=f"orchestrator-issue-effect:{run_id}:dispatch",
            run_id=run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=admission_ref,
            publication_timestamp=created_at,
            intended_target_ref=f"issue:{issue_id}",
            observed_result_ref=admission_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=admission_ref,
        )

    async def _close_active_dispatch(
        self,
        *,
        session_id: str,
        issue_id: str,
        current_status: CardStatus | str,
        target_status: CardStatus | str,
        reason: str,
        observation_only: bool = False,
    ) -> bool:
        latest = await self.publication.repository.get_latest_reservation_record_for_holder_ref(
            holder_ref=holder_ref_for_issue(session_id=session_id, issue_id=issue_id)
        )
        if latest is None or latest.status is not ReservationStatus.PROMOTED_TO_LEASE:
            return False
        run_id = run_id_from_reservation_id(reservation_id=latest.reservation_id)
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None or run.final_truth_record_id is not None:
            return False
        attempt = await self.execution_repository.get_attempt_record(attempt_id=str(run.current_attempt_id or ""))
        if attempt is None:
            raise OrchestratorIssueControlPlaneError(f"orchestrator issue dispatch missing attempt: {run_id}")
        closeout_ref = (
            observation_ref(
                session_id=session_id,
                issue_id=issue_id,
                status=target_status,
                reason=reason,
            )
            if observation_only
            else transition_ref(
                session_id=session_id,
                issue_id=issue_id,
                from_status=current_status,
                to_status=target_status,
                reason=reason,
            )
        )
        step = await self.execution_repository.save_step_record(
            record=StepRecord(
                step_id=f"{run_id}:step:closeout",
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
        if not observation_only:
            await self._append_closeout_effect(
                run_id=run_id,
                attempt_id=attempt.attempt_id,
                step=step,
                issue_id=issue_id,
            )
        attempt_state, run_state, result_class, completion_classification, closure_basis = classify_closeout(
            target_status=target_status,
            reason=reason,
        )
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=attempt_state)
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=run_state)
        ended_at = utc_now()
        truth = await self.publication.publish_final_truth(
            final_truth_record_id=f"orchestrator-issue-final-truth:{run_id}",
            run_id=run_id,
            result_class=result_class,
            completion_classification=completion_classification,
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=closure_basis,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
            authoritative_result_ref=closeout_ref,
        )
        await self.execution_repository.save_attempt_record(
            record=attempt.model_copy(update={"attempt_state": attempt_state, "end_timestamp": ended_at})
        )
        await self.execution_repository.save_run_record(
            record=run.model_copy(update={"lifecycle_state": run_state, "final_truth_record_id": truth.final_truth_record_id})
        )
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            await self.publication.publish_lease(
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
        return True

    async def _append_closeout_effect(self, *, run_id: str, attempt_id: str, step: StepRecord, issue_id: str) -> None:
        existing = await self.publication.repository.list_effect_journal_entries(run_id=run_id)
        if any(entry.step_id == step.step_id for entry in existing):
            return
        await self.publication.append_effect_journal_entry(
            journal_entry_id=f"orchestrator-issue-journal:{run_id}:closeout",
            effect_id=f"orchestrator-issue-effect:{run_id}:closeout",
            run_id=run_id,
            attempt_id=attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=step.output_ref or step.input_ref,
            publication_timestamp=utc_now(),
            intended_target_ref=f"issue:{issue_id}",
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or step.input_ref,
        )

__all__ = ["OrchestratorIssueControlPlaneError", "OrchestratorIssueControlPlaneService"]
