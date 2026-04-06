from __future__ import annotations

from typing import TypedDict

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.application.services.control_plane_workload_catalog import (
    ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    child_workload_holder_ref_for_issue,
    child_workload_run_id_for_issue_creation,
    classify_closeout,
    issue_creation_ref,
    lease_id_for_run,
    namespace_scope,
    resources_touched,
    scheduler_holder_ref_for_issue,
    scheduler_run_id_for_transition,
    status_ref,
    transition_ref,
    utc_now,
)
from orket.core.contracts import RunRecord, WorkloadRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    LeaseStatus,
    ReservationStatus,
    ResultClass,
    RunState,
)
from orket.core.domain.control_plane_lifecycle import is_terminal_attempt_state
from orket.schema import CardStatus

from .orchestrator_scheduler_control_plane_mutation import (
    activate_namespace_authority,
    close_namespace_mutation,
    create_namespace_execution,
    publish_mutation_step_and_effect,
)


class SchedulerNamespaceMutation(TypedDict):
    run_id: str
    workload: WorkloadRecord
    holder_ref: str
    issue_id: str
    admission_ref: str
    policy_payload: dict[str, object]
    config_payload: dict[str, object]
    step_kind: str
    input_ref: str
    output_ref: str
    capability_used: CapabilityClass
    resources: list[str]
    observed_result_classification: str
    intended_target_ref: str
    result_class: ResultClass
    completion_classification: CompletionClassification
    closure_basis: ClosureBasisClassification


class OrchestratorSchedulerControlPlaneService:
    """Publishes scheduler-owned namespace authority for orchestrator issue mutations."""

    TRANSITION_WORKLOAD = ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD
    CHILD_WORKLOAD = ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD
    PROMOTION_RULE = "promote_on_scheduler_mutation_start"
    CLEANUP_RULE = "release_on_scheduler_mutation_closeout"

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def publish_scheduler_transition(
        self,
        *,
        session_id: str,
        issue_id: str,
        current_status: CardStatus | str,
        target_status: CardStatus | str,
        reason: str,
        assignee: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        normalized_session_id = str(session_id or "").strip()
        normalized_issue_id = str(issue_id or "").strip()
        normalized_reason = str(reason or "").strip().lower()
        if not normalized_session_id or not normalized_issue_id or not normalized_reason:
            return None
        mutation = self._scheduler_transition_mutation(
            session_id=normalized_session_id,
            issue_id=normalized_issue_id,
            current_status=current_status,
            target_status=target_status,
            reason=normalized_reason,
            assignee=assignee,
            metadata=dict(metadata or {}),
        )
        return await self._publish_namespace_mutation(**mutation)

    async def publish_child_issue_creation(
        self,
        *,
        session_id: str,
        issue_id: str,
        active_build: str,
        seat_name: str,
        relationship_class: str,
        trigger_issue_ids: list[str],
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        normalized_session_id = str(session_id or "").strip()
        normalized_issue_id = str(issue_id or "").strip()
        normalized_relationship = str(relationship_class or "").strip().lower()
        if not normalized_session_id or not normalized_issue_id or not normalized_relationship:
            return None
        mutation = self._child_issue_creation_mutation(
            session_id=normalized_session_id,
            issue_id=normalized_issue_id,
            active_build=active_build,
            seat_name=seat_name,
            relationship_class=normalized_relationship,
            trigger_issue_ids=list(trigger_issue_ids),
            metadata=dict(metadata or {}),
        )
        return await self._publish_namespace_mutation(**mutation)

    def _scheduler_transition_mutation(
        self,
        *,
        session_id: str,
        issue_id: str,
        current_status: CardStatus | str,
        target_status: CardStatus | str,
        reason: str,
        assignee: str | None,
        metadata: dict[str, object],
    ) -> SchedulerNamespaceMutation:
        holder_ref = scheduler_holder_ref_for_issue(session_id=session_id, issue_id=issue_id)
        admission_ref = transition_ref(
            session_id=session_id,
            issue_id=issue_id,
            from_status=current_status,
            to_status=target_status,
            reason=reason,
        )
        result_class, completion_classification, closure_basis = classify_closeout(
            target_status=target_status,
            reason=reason,
        )[2:]
        return {
            "run_id": scheduler_run_id_for_transition(
                session_id=session_id,
                issue_id=issue_id,
                current_status=current_status,
                target_status=target_status,
                reason=reason,
                metadata=metadata,
            ),
            "workload": self.TRANSITION_WORKLOAD,
            "holder_ref": holder_ref,
            "issue_id": issue_id,
            "admission_ref": admission_ref,
            "policy_payload": {
                "reason": reason,
                "holder_ref": holder_ref,
                "namespace_scope": namespace_scope(issue_id=issue_id),
                "scheduling_class": "scheduler_owned_issue_transition",
            },
            "config_payload": {
                "session_id": session_id,
                "issue_id": issue_id,
                "assignee": str(assignee or "").strip() or None,
                "current_status": str(current_status.value if hasattr(current_status, "value") else current_status),
                "target_status": str(target_status.value if hasattr(target_status, "value") else target_status),
                "metadata": metadata,
            },
            "step_kind": "issue_status_transition",
            "input_ref": status_ref(session_id=session_id, issue_id=issue_id, status=current_status),
            "output_ref": admission_ref,
            "capability_used": CapabilityClass.BOUNDED_LOCAL_MUTATION,
            "resources": resources_touched(issue_id=issue_id),
            "observed_result_classification": f"issue_scheduler_transition:{reason}",
            "intended_target_ref": f"issue:{issue_id}",
            "result_class": result_class,
            "completion_classification": completion_classification,
            "closure_basis": closure_basis,
        }

    def _child_issue_creation_mutation(
        self,
        *,
        session_id: str,
        issue_id: str,
        active_build: str,
        seat_name: str,
        relationship_class: str,
        trigger_issue_ids: list[str],
        metadata: dict[str, object],
    ) -> SchedulerNamespaceMutation:
        holder_ref = child_workload_holder_ref_for_issue(session_id=session_id, issue_id=issue_id)
        creation_receipt_ref = issue_creation_ref(
            session_id=session_id,
            issue_id=issue_id,
            relationship_class=relationship_class,
        )
        return {
            "run_id": child_workload_run_id_for_issue_creation(
                session_id=session_id,
                child_issue_id=issue_id,
                relationship_class=relationship_class,
                metadata={
                    "active_build": active_build,
                    "seat_name": seat_name,
                    "trigger_issue_ids": list(trigger_issue_ids),
                    **metadata,
                },
            ),
            "workload": self.CHILD_WORKLOAD,
            "holder_ref": holder_ref,
            "issue_id": issue_id,
            "admission_ref": creation_receipt_ref,
            "policy_payload": {
                "relationship_class": relationship_class,
                "namespace_inheritance_rule": "new_child_issue_namespace",
                "capability_escalation_policy": "no_ambient_escalation",
                "reservation_interaction_rule": "explicit_namespace_reservation_then_lease",
                "final_truth_publication_rule": "parent_records_child_creation_only",
            },
            "config_payload": {
                "session_id": session_id,
                "issue_id": issue_id,
                "active_build": str(active_build or "").strip(),
                "seat_name": str(seat_name or "").strip(),
                "trigger_issue_ids": list(trigger_issue_ids),
                "metadata": metadata,
            },
            "step_kind": "create_child_issue",
            "input_ref": f"build:{session_id}:{str(active_build or '').strip() or 'unknown'}",
            "output_ref": creation_receipt_ref,
            "capability_used": CapabilityClass.BOUNDED_LOCAL_MUTATION,
            "resources": resources_touched(issue_id=issue_id, related_issue_ids=list(trigger_issue_ids)),
            "observed_result_classification": f"child_issue_created:{relationship_class}",
            "intended_target_ref": f"issue:{issue_id}",
            "result_class": ResultClass.SUCCESS,
            "completion_classification": CompletionClassification.SATISFIED,
            "closure_basis": ClosureBasisClassification.NORMAL_EXECUTION,
        }

    async def _publish_namespace_mutation(
        self,
        *,
        run_id: str,
        workload: WorkloadRecord,
        holder_ref: str,
        issue_id: str,
        admission_ref: str,
        policy_payload: dict[str, object],
        config_payload: dict[str, object],
        step_kind: str,
        input_ref: str,
        output_ref: str,
        capability_used: CapabilityClass,
        resources: list[str],
        observed_result_classification: str,
        intended_target_ref: str,
        result_class: ResultClass,
        completion_classification: CompletionClassification,
        closure_basis: ClosureBasisClassification,
    ) -> str:
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is not None:
            await self._require_closed_existing_run(
                run_id=run_id,
                expected_namespace_scope=namespace_scope(issue_id=issue_id),
            )
            return run_id
        created_at = utc_now()
        run, attempt = await create_namespace_execution(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run_id=run_id,
            workload=workload,
            issue_id=issue_id,
            admission_ref=admission_ref,
            policy_payload=policy_payload,
            config_payload=config_payload,
            created_at=created_at,
        )
        attempt_id = attempt.attempt_id
        run, attempt, _reservation, lease = await activate_namespace_authority(
            execution_repository=self.execution_repository,
            publication=self.publication,
            promotion_rule=self.PROMOTION_RULE,
            cleanup_rule=self.CLEANUP_RULE,
            run=run,
            attempt=attempt,
            workload=workload,
            holder_ref=holder_ref,
            issue_id=issue_id,
            step_kind=step_kind,
            created_at=created_at,
        )
        await publish_mutation_step_and_effect(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            workload=workload,
            admission_ref=admission_ref,
            attempt_id=attempt_id,
            step_kind=step_kind,
            input_ref=input_ref,
            output_ref=output_ref,
            capability_used=capability_used,
            resources=resources,
            observed_result_classification=observed_result_classification,
            intended_target_ref=intended_target_ref,
            created_at=created_at,
        )
        await close_namespace_mutation(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            attempt=attempt,
            lease=lease,
            workload=workload,
            step_kind=step_kind,
            output_ref=output_ref,
            result_class=result_class,
            completion_classification=completion_classification,
            closure_basis=closure_basis,
            ended_at=utc_now(),
        )
        return run_id

    async def _require_closed_existing_run(self, *, run_id: str, expected_namespace_scope: str) -> None:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            return
        if run.final_truth_record_id is None:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation already has active control-plane truth: {run_id}"
            )
        await self._require_closed_run_resource_authority(run=run)
        run_scope = str(run.namespace_scope or "").strip()
        expected_scope = str(expected_namespace_scope or "").strip()
        if not run_scope or run_scope != expected_scope:
            raise OrchestratorSchedulerControlPlaneError(
                "orchestrator scheduler mutation closed run namespace scope drift: "
                f"{run_id};run_scope={run_scope!r};expected_scope={expected_scope!r}"
            )
        if run.lifecycle_state not in {RunState.COMPLETED, RunState.FAILED_TERMINAL, RunState.CANCELLED}:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run has non-terminal lifecycle: {run_id}"
            )
        current_attempt_id = str(run.current_attempt_id or "").strip()
        if not current_attempt_id:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run missing current attempt id: {run_id}"
            )
        attempt = await self.execution_repository.get_attempt_record(attempt_id=current_attempt_id)
        if attempt is None:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run missing attempt: {run_id}"
            )
        if not is_terminal_attempt_state(attempt.attempt_state):
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run has non-terminal attempt: {run_id}"
            )

    async def _require_closed_run_resource_authority(self, *, run: RunRecord) -> None:
        workload_id = str(run.workload_id or "").strip()
        run_id = str(run.run_id or "").strip()
        reservation_id = f"{workload_id}-reservation:{run_id}"
        reservation = await self.publication.repository.get_latest_reservation_record(reservation_id=reservation_id)
        if reservation is None:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run missing reservation authority: {run_id}"
            )
        if reservation.status is ReservationStatus.ACTIVE:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run has active reservation drift: {run_id}"
            )
        lease = await self.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
        if lease is not None and lease.status is LeaseStatus.ACTIVE:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run has active lease drift: {run_id}"
            )
        if reservation.status is ReservationStatus.PROMOTED_TO_LEASE and lease is None:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run missing lease authority for promoted reservation: {run_id}"
            )
        if lease is not None and lease.source_reservation_id != reservation.reservation_id:
            raise OrchestratorSchedulerControlPlaneError(
                f"orchestrator scheduler mutation closed run lease source mismatch: {run_id}"
            )
        if lease is not None:
            resource = await self.publication.repository.get_latest_resource_record(resource_id=lease.resource_id)
            require_resource_snapshot_matches_lease(
                resource=resource,
                lease=lease,
                expected_resource_kind="scheduler_namespace",
                expected_namespace_scope=str(run.namespace_scope or "").strip(),
                error_context=f"orchestrator scheduler mutation closed run {run_id}",
                error_factory=OrchestratorSchedulerControlPlaneError,
            )


class OrchestratorSchedulerControlPlaneError(ValueError):
    """Raised when scheduler-owned control-plane publication detects non-terminal run-state drift."""


__all__ = ["OrchestratorSchedulerControlPlaneError", "OrchestratorSchedulerControlPlaneService"]
