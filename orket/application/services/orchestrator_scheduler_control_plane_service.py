from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_support import (
    child_workload_holder_ref_for_issue,
    child_workload_run_id_for_issue_creation,
    classify_closeout,
    issue_creation_ref,
    namespace_scope,
    resources_touched,
    scheduler_holder_ref_for_issue,
    scheduler_run_id_for_transition,
    status_ref,
    transition_ref,
    utc_now,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import CapabilityClass, ClosureBasisClassification, CompletionClassification, ResultClass
from orket.schema import CardStatus

from .orchestrator_scheduler_control_plane_mutation import (
    activate_namespace_authority,
    close_namespace_mutation,
    create_namespace_execution,
    publish_mutation_step_and_effect,
)


class OrchestratorSchedulerControlPlaneService:
    """Publishes scheduler-owned namespace authority for orchestrator issue mutations."""

    TRANSITION_WORKLOAD_ID = "orchestrator-issue-scheduler"
    TRANSITION_WORKLOAD_VERSION = "orchestrator.issue_scheduler.v1"
    CHILD_WORKLOAD_ID = "orchestrator-child-workload-composition"
    CHILD_WORKLOAD_VERSION = "orchestrator.child_workload_composition.v1"
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
    ) -> dict[str, object]:
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
            "workload_id": self.TRANSITION_WORKLOAD_ID,
            "workload_version": self.TRANSITION_WORKLOAD_VERSION,
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
    ) -> dict[str, object]:
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
            "workload_id": self.CHILD_WORKLOAD_ID,
            "workload_version": self.CHILD_WORKLOAD_VERSION,
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
        workload_id: str,
        workload_version: str,
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
            return run_id
        created_at = utc_now()
        run, attempt = await create_namespace_execution(
            execution_repository=self.execution_repository,
            run_id=run_id,
            workload_id=workload_id,
            workload_version=workload_version,
            issue_id=issue_id,
            admission_ref=admission_ref,
            policy_payload=policy_payload,
            config_payload=config_payload,
            created_at=created_at,
        )
        attempt_id = attempt.attempt_id
        _reservation, lease = await activate_namespace_authority(
            execution_repository=self.execution_repository,
            publication=self.publication,
            promotion_rule=self.PROMOTION_RULE,
            cleanup_rule=self.CLEANUP_RULE,
            run=run,
            attempt=attempt,
            workload_id=workload_id,
            holder_ref=holder_ref,
            issue_id=issue_id,
            step_kind=step_kind,
            created_at=created_at,
        )
        await publish_mutation_step_and_effect(
            execution_repository=self.execution_repository,
            publication=self.publication,
            run=run,
            workload_id=workload_id,
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
            workload_id=workload_id,
            step_kind=step_kind,
            output_ref=output_ref,
            result_class=result_class,
            completion_classification=completion_classification,
            closure_basis=closure_basis,
            ended_at=utc_now(),
        )
        return run_id


__all__ = ["OrchestratorSchedulerControlPlaneService"]
