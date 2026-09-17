from __future__ import annotations

from collections.abc import Callable

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots
from orket.application.services.control_plane_workload_catalog import (
    ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
)
from orket.application.services.orchestrator_issue_closeout import close_active_dispatch
from orket.application.services.orchestrator_issue_control_plane_support import (
    attempt_id_for_run,
    digest,
    holder_ref_for_issue,
    lease_id_for_run,
    namespace_scope,
    reservation_id_for_run,
    resource_id,
    resources_touched,
    run_id_for_dispatch,
    run_id_from_reservation_id,
    status_ref,
    status_token,
    transition_ref,
)
from orket.core.contracts import AttemptRecord, LeaseRecord, RunRecord, StepRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    CapabilityClass,
    CleanupAuthorityClass,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    RunState,
    is_terminal_attempt_state,
    is_terminal_run_state,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.core.domain.control_plane_final_truth import validate_terminal_record_consistency
from orket.schema import CardStatus


class OrchestratorIssueControlPlaneError(ValueError):
    """Raised when orchestrator issue-dispatch control-plane truth cannot be published honestly."""


class OrchestratorIssueControlPlaneService:
    """Publishes shared issue-dispatch reservation, lease, step, effect, and closeout truth."""

    WORKLOAD = ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD
    PROMOTION_RULE = "promote_on_issue_turn_dispatch"
    CLEANUP_RULE = "release_on_issue_dispatch_closeout"

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
        transactions: ControlPlaneTransactionFactory,
        now_utc: Callable[[], str],
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication
        self.transactions = transactions
        self.now_utc = now_utc

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
            await self._require_closed_existing_dispatch_run(
                run_id=run_id,
                expected_namespace_scope=namespace_scope(issue_id=issue_id),
            )
            return
        created_at = self.now_utc()
        admission_ref = transition_ref(
            session_id=session_id,
            issue_id=issue_id,
            from_status=current_status,
            to_status=target_status,
            reason="turn_dispatch",
        )
        policy_payload = {"reason": "turn_dispatch", "review_turn": review_turn}
        configuration_payload = {
            "session_id": session_id,
            "issue_id": issue_id,
            "seat_name": seat_name,
            "turn_index": turn_index,
            "review_turn": review_turn,
            "from_status": status_token(current_status),
            "to_status": status_token(target_status),
        }
        run = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD.workload_id,
            workload_version=self.WORKLOAD.workload_version,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest=digest(policy_payload),
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest=digest(configuration_payload),
            creation_timestamp=created_at,
            admission_decision_receipt_ref=admission_ref,
            namespace_scope=namespace_scope(issue_id=issue_id),
            lifecycle_state=RunState.ADMISSION_PENDING,
            current_attempt_id=attempt_id_for_run(run_id=run_id),
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[admission_ref],
            configuration_payload=configuration_payload,
            configuration_source_refs=[admission_ref],
        )
        attempt = AttemptRecord(
            attempt_id=attempt_id_for_run(run_id=run_id),
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.CREATED,
            starting_state_snapshot_ref=admission_ref,
            start_timestamp=created_at,
        )
        run = await self.execution_repository.save_run_record(record=run)
        attempt = await self.execution_repository.save_attempt_record(record=attempt)
        reservation = await self.publication.publish_reservation(
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
        try:
            validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.ADMITTED)
            run = run.model_copy(update={"lifecycle_state": RunState.ADMITTED})
            run = await self.execution_repository.save_run_record(record=run)
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
            await self._publish_resource_snapshot(run=run, lease=lease)
            await self.publication.promote_reservation_to_lease(
                reservation_id=reservation.reservation_id,
                promoted_lease_id=lease.lease_id,
                supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:promote_dispatch_lease",
                promotion_basis="issue_turn_dispatch_started",
            )
            validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
            run = await self.execution_repository.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
            attempt = await self.execution_repository.save_attempt_record(
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
        except Exception:
            await self._rollback_begin_dispatch_authority(run_id=run_id, reservation_id=reservation.reservation_id)
            raise

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
        async with self.transactions() as transaction:
            owner = OrchestratorIssueControlPlaneService(
                execution_repository=transaction.execution,
                publication=ControlPlanePublicationService(
                    repository=transaction.records, authority=self.publication.authority),
                transactions=self.transactions,
                now_utc=self.now_utc,
            )
            return await close_active_dispatch(
                owner, session_id=session_id, issue_id=issue_id, current_status=current_status,
                target_status=target_status, reason=reason, observation_only=observation_only,
                ended_at=self.now_utc(), error_type=OrchestratorIssueControlPlaneError,
            )

    async def _require_closed_existing_dispatch_run(
        self,
        *,
        run_id: str,
        expected_namespace_scope: str,
    ) -> None:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            return
        if run.final_truth_record_id is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch already has active control-plane truth: {run_id}"
            )
        self._require_namespace_scope(
            run=run,
            expected_namespace_scope=expected_namespace_scope,
            error_context="closed run namespace scope drift",
        )
        await self._require_closed_dispatch_resource_authority(run=run)
        if not is_terminal_run_state(run.lifecycle_state):
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run has non-terminal lifecycle: {run_id}"
            )
        current_attempt_id = str(run.current_attempt_id or "").strip()
        if not current_attempt_id:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run missing current attempt id: {run_id}"
            )
        attempt = await self.execution_repository.get_attempt_record(attempt_id=current_attempt_id)
        if attempt is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run missing attempt: {run_id}"
            )
        if not is_terminal_attempt_state(attempt.attempt_state):
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run has non-terminal attempt: {run_id}"
            )
        truth = await self.publication.repository.get_final_truth(run_id=run_id)
        validate_terminal_record_consistency(run, attempt, truth)

    def _require_active_dispatch_run_attempt(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        expected_namespace_scope: str,
    ) -> None:
        if str(attempt.run_id or "").strip() != run.run_id:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch attempt run mismatch: run={run.run_id} attempt={attempt.attempt_id}"
            )
        self._require_namespace_scope(
            run=run,
            expected_namespace_scope=expected_namespace_scope,
            error_context="active run namespace scope drift",
        )
        if is_terminal_run_state(run.lifecycle_state):
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active reservation points to terminal run drift: {run.run_id}"
            )
        if is_terminal_attempt_state(attempt.attempt_state):
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run has terminal attempt drift: {run.run_id}:{attempt.attempt_id}"
            )

    def _require_namespace_scope(
        self,
        *,
        run: RunRecord,
        expected_namespace_scope: str,
        error_context: str,
    ) -> None:
        run_scope = str(run.namespace_scope or "").strip()
        expected_scope = str(expected_namespace_scope or "").strip()
        if not run_scope or run_scope != expected_scope:
            raise OrchestratorIssueControlPlaneError(
                "orchestrator issue dispatch "
                f"{error_context}: run={run.run_id} run_scope={run_scope!r} expected_scope={expected_scope!r}"
            )

    async def _require_active_dispatch_resource_authority(self, *, run: RunRecord) -> None:
        reservation_id = reservation_id_for_run(run_id=run.run_id)
        reservation = await self.publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
        if reservation is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run missing reservation authority: {run.run_id}"
            )
        if reservation.status is not ReservationStatus.PROMOTED_TO_LEASE:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run has non-promoted reservation drift: {run.run_id}"
            )
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
        if lease is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run missing lease authority: {run.run_id}"
            )
        if lease.status is not LeaseStatus.ACTIVE:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run has non-active lease drift: {run.run_id}"
            )
        if lease.source_reservation_id != reservation.reservation_id:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch active run lease source mismatch: {run.run_id}"
            )
        resource = await self.publication.repository.get_latest_resource_record(resource_id=lease.resource_id)
        require_resource_snapshot_matches_lease(
            resource=resource,
            lease=lease,
            expected_resource_kind="issue_dispatch_slot",
            expected_namespace_scope=str(run.namespace_scope or "").strip(),
            error_context=f"orchestrator issue dispatch active run {run.run_id}",
            error_factory=OrchestratorIssueControlPlaneError,
        )

    async def _require_closed_dispatch_resource_authority(self, *, run: RunRecord) -> None:
        reservation_id = reservation_id_for_run(run_id=run.run_id)
        reservation = await self.publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
        if reservation is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run missing reservation authority: {run.run_id}"
            )
        if reservation.status is ReservationStatus.ACTIVE:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run has active reservation drift: {run.run_id}"
            )
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run has active lease drift: {run.run_id}"
            )
        if reservation.status is ReservationStatus.PROMOTED_TO_LEASE and lease is None:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run missing lease authority for promoted reservation: {run.run_id}"
            )
        if lease is not None and lease.source_reservation_id != reservation.reservation_id:
            raise OrchestratorIssueControlPlaneError(
                f"orchestrator issue dispatch closed run lease source mismatch: {run.run_id}"
            )
        if lease is not None:
            resource = await self.publication.repository.get_latest_resource_record(resource_id=lease.resource_id)
            require_resource_snapshot_matches_lease(
                resource=resource,
                lease=lease,
                expected_resource_kind="issue_dispatch_slot",
                expected_namespace_scope=str(run.namespace_scope or "").strip(),
                error_context=f"orchestrator issue dispatch closed run {run.run_id}",
                error_factory=OrchestratorIssueControlPlaneError,
            )

    async def _rollback_begin_dispatch_authority(self, *, run_id: str, reservation_id: str) -> None:
        failed_at = self.now_utc()
        run = await self.execution_repository.get_run_record(run_id=run_id)
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            released = await self.publication.publish_lease(
                lease_id=lease.lease_id,
                resource_id=lease.resource_id,
                holder_ref=lease.holder_ref,
                lease_epoch=lease.lease_epoch,
                publication_timestamp=failed_at,
                expiry_basis="issue_turn_dispatch_begin_failed",
                status=LeaseStatus.RELEASED,
                cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
                last_confirmed_observation=lease.last_confirmed_observation,
                source_reservation_id=lease.source_reservation_id,
            )
            if run is not None:
                await self._publish_resource_snapshot(run=run, lease=released)
        reservation = await self.publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
        if reservation is not None and reservation.status is ReservationStatus.ACTIVE:
            await self.publication.invalidate_reservation(
                reservation_id=reservation_id,
                supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:dispatch_fail_closeout",
                invalidation_basis="issue_turn_dispatch_begin_failed",
            )

    async def _publish_resource_snapshot(self, *, run: RunRecord, lease: LeaseRecord) -> None:
        namespace = str(run.namespace_scope or "").strip() or lease.resource_id
        await self.publication.publish_resource(
            resource_id=str(lease.resource_id),
            resource_kind="issue_dispatch_slot",
            namespace_scope=namespace,
            ownership_class=OwnershipClass.RUN_OWNED,
            current_observed_state=f"lease_status:{lease.status.value};namespace:{namespace}",
            last_observed_timestamp=lease.publication_timestamp,
            cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
            provenance_ref=lease.last_confirmed_observation or lease.lease_id,
            reconciliation_status="governed_execution_authority",
            orphan_classification=OrphanClassification.NOT_ORPHANED,
        )

__all__ = ["OrchestratorIssueControlPlaneError", "OrchestratorIssueControlPlaneService"]
