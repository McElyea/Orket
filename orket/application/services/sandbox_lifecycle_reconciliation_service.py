from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from orket.application.services.sandbox_control_plane_reconciliation_service import (
    SandboxControlPlaneReconciliationService,
)
from orket.application.services.sandbox_control_plane_resource_service import (
    SandboxControlPlaneResourceService,
)
from orket.application.services.sandbox_lifecycle_mutation_service import (
    SandboxLifecycleMutationResult,
    SandboxLifecycleMutationService,
)
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.domain.sandbox_lifecycle import (
    CleanupState,
    LifecycleEvent,
    OwnershipConfidence,
    ReconciliationClassification,
    SandboxLifecycleError,
    SandboxState,
    TerminalReason,
    classify_reconciliation,
)
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord

if TYPE_CHECKING:
    from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
    from orket.application.services.sandbox_control_plane_checkpoint_service import (
        SandboxControlPlaneCheckpointService,
    )
    from orket.application.services.sandbox_control_plane_execution_service import (
        SandboxControlPlaneExecutionService,
    )


@dataclass(frozen=True)
class SandboxObservation:
    docker_present: bool
    observed_at: str
    ownership_confidence: OwnershipConfidence | None = None


@dataclass(frozen=True)
class SandboxReconciliationPlan:
    classification: ReconciliationClassification
    target_state: SandboxState
    target_cleanup_state: CleanupState | None
    terminal_reason: TerminalReason | None
    cleanup_due_at: str | None
    action_required: bool


class SandboxLifecycleReconciliationService:
    """Deterministic reconciliation planner for durable sandbox lifecycle state."""

    def __init__(
        self,
        *,
        mutation_service: SandboxLifecycleMutationService,
        policy: SandboxLifecyclePolicy | None = None,
        control_plane_publication: ControlPlanePublicationService | None = None,
        control_plane_execution: SandboxControlPlaneExecutionService | None = None,
        control_plane_checkpoints: SandboxControlPlaneCheckpointService | None = None,
    ):
        self.mutation_service = mutation_service
        self.policy = policy or SandboxLifecyclePolicy()
        self.control_plane_publication = control_plane_publication
        self.control_plane_execution = control_plane_execution
        self.control_plane_checkpoints = control_plane_checkpoints
        if (
            self.control_plane_checkpoints is None
            and self.control_plane_publication is not None
            and self.control_plane_execution is not None
        ):
            from orket.application.services.sandbox_control_plane_checkpoint_service import (
                SandboxControlPlaneCheckpointService,
            )

            self.control_plane_checkpoints = SandboxControlPlaneCheckpointService(
                publication=self.control_plane_publication,
                lifecycle_repository=self.mutation_service.repository,
                execution_repository=self.control_plane_execution.repository,
            )

    async def reconcile_existing_record(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        observation: SandboxObservation,
    ) -> SandboxLifecycleMutationResult | None:
        record = await self._require_record(sandbox_id)
        plan = self.plan_existing_record(record=record, observation=observation)
        if not plan.action_required:
            return None
        if plan.classification is ReconciliationClassification.RECLAIMABLE:
            result = await self.mutation_service.transition_state(
                sandbox_id=sandbox_id,
                operation_id=operation_id,
                expected_record_version=record.record_version,
                event=LifecycleEvent.LEASE_EXPIRED,
                next_state=SandboxState.RECLAIMABLE,
                terminal_reason=TerminalReason.LEASE_EXPIRED,
                next_owner_instance_id=record.owner_instance_id,
                next_lease_epoch=record.lease_epoch,
                cleanup_due_at=plan.cleanup_due_at,
            )
            await self._publish_resource_state_change(record=result.record, observed_at=observation.observed_at)
            await self._publish_reconciliation_state_change(
                classification=plan.classification,
                record=result.record,
                observed_at=observation.observed_at,
            )
            await self._publish_execution_waiting_on_resource(
                record=result.record,
                observed_at=observation.observed_at,
            )
            return result
        if plan.classification is ReconciliationClassification.TERMINAL_LOST_RUNTIME:
            result = await self.mutation_service.transition_state(
                sandbox_id=sandbox_id,
                operation_id=operation_id,
                expected_record_version=record.record_version,
                event=LifecycleEvent.RUNTIME_MISSING,
                next_state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.LOST_RUNTIME,
                cleanup_due_at=plan.cleanup_due_at,
            )
            await self._publish_resource_state_change(record=result.record, observed_at=observation.observed_at)
            await self._publish_lost_runtime_control_plane_closure(
                record=result.record,
                observed_at=observation.observed_at,
            )
            return result
        if plan.classification is ReconciliationClassification.CLEANED_EXTERNALLY:
            result = await self.mutation_service.transition_state(
                sandbox_id=sandbox_id,
                operation_id=operation_id,
                expected_record_version=record.record_version,
                event=LifecycleEvent.EXTERNAL_ABSENCE_VERIFIED,
                next_state=SandboxState.CLEANED,
                terminal_reason=TerminalReason.CLEANED_EXTERNALLY,
                cleanup_state=CleanupState.COMPLETED,
            )
            await self._publish_resource_state_change(record=result.record, observed_at=observation.observed_at)
            await self._publish_reconciliation_state_change(
                classification=plan.classification,
                record=result.record,
                observed_at=observation.observed_at,
            )
            return result
        if plan.classification in {
            ReconciliationClassification.TERMINAL_AWAITING_CLEANUP,
            ReconciliationClassification.CLEANUP_OVERDUE,
        }:
            return await self.mutation_service.transition_state(
                sandbox_id=sandbox_id,
                operation_id=operation_id,
                expected_record_version=record.record_version,
                event=LifecycleEvent.CLEANUP_SCHEDULED,
                next_state=SandboxState.TERMINAL,
                cleanup_state=CleanupState.SCHEDULED,
                cleanup_due_at=plan.cleanup_due_at,
            )
        raise SandboxLifecycleError(f"Unsupported reconciliation mutation for {plan.classification.value}.")

    def plan_existing_record(
        self,
        *,
        record: SandboxLifecycleRecord,
        observation: SandboxObservation,
    ) -> SandboxReconciliationPlan:
        classification = classify_reconciliation(
            durable_state=record.state,
            docker_present=observation.docker_present,
            ownership_confidence=observation.ownership_confidence,
            lease_expired=self._is_due(record.lease_expires_at, observation.observed_at),
            cleanup_due_passed=self._is_due(record.cleanup_due_at, observation.observed_at),
        )
        if classification.classification is ReconciliationClassification.ACTIVE:
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=record.state,
                target_cleanup_state=record.cleanup_state,
                terminal_reason=record.terminal_reason,
                cleanup_due_at=record.cleanup_due_at,
                action_required=False,
            )
        if classification.classification is ReconciliationClassification.RECLAIMABLE:
            due = self.policy.cleanup_due_at_for(
                state=SandboxState.RECLAIMABLE,
                terminal_reason=TerminalReason.LEASE_EXPIRED,
                reference_time=observation.observed_at,
            )
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=SandboxState.RECLAIMABLE,
                target_cleanup_state=record.cleanup_state,
                terminal_reason=TerminalReason.LEASE_EXPIRED,
                cleanup_due_at=due,
                action_required=record.state is not SandboxState.RECLAIMABLE or record.cleanup_due_at != due,
            )
        if classification.classification is ReconciliationClassification.TERMINAL_LOST_RUNTIME:
            due = self.policy.cleanup_due_at_for(
                state=SandboxState.TERMINAL,
                terminal_reason=TerminalReason.LOST_RUNTIME,
                reference_time=observation.observed_at,
            )
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=SandboxState.TERMINAL,
                target_cleanup_state=record.cleanup_state,
                terminal_reason=TerminalReason.LOST_RUNTIME,
                cleanup_due_at=due,
                action_required=record.terminal_reason is not TerminalReason.LOST_RUNTIME
                or record.cleanup_due_at != due,
            )
        if classification.classification is ReconciliationClassification.TERMINAL_AWAITING_CLEANUP:
            reason = record.terminal_reason or TerminalReason.FAILED
            due = record.cleanup_due_at or self.policy.cleanup_due_at_for(
                state=SandboxState.TERMINAL,
                terminal_reason=reason,
                reference_time=record.terminal_at or observation.observed_at,
            )
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=SandboxState.TERMINAL,
                target_cleanup_state=CleanupState.SCHEDULED,
                terminal_reason=reason,
                cleanup_due_at=due,
                action_required=record.cleanup_state is CleanupState.NONE,
            )
        if classification.classification is ReconciliationClassification.CLEANUP_OVERDUE:
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=SandboxState.TERMINAL,
                target_cleanup_state=CleanupState.SCHEDULED,
                terminal_reason=record.terminal_reason,
                cleanup_due_at=record.cleanup_due_at,
                action_required=record.cleanup_state is CleanupState.NONE,
            )
        if classification.classification is ReconciliationClassification.CLEANED_EXTERNALLY:
            return SandboxReconciliationPlan(
                classification=classification.classification,
                target_state=SandboxState.CLEANED,
                target_cleanup_state=CleanupState.COMPLETED,
                terminal_reason=TerminalReason.CLEANED_EXTERNALLY,
                cleanup_due_at=record.cleanup_due_at,
                action_required=record.state is not SandboxState.CLEANED
                or record.cleanup_state is not CleanupState.COMPLETED
                or record.terminal_reason is not TerminalReason.CLEANED_EXTERNALLY,
            )
        raise SandboxLifecycleError(
            f"Unsupported reconciliation classification: {classification.classification.value}."
        )

    def plan_missing_record_presence(
        self,
        *,
        observation: SandboxObservation,
    ) -> SandboxReconciliationPlan:
        if not observation.docker_present or observation.ownership_confidence is None:
            raise SandboxLifecycleError(
                "Missing-record reconciliation requires present Docker resources and ownership confidence."
            )
        classification = classify_reconciliation(
            durable_state=None,
            docker_present=True,
            ownership_confidence=observation.ownership_confidence,
        )
        reason = classification.terminal_reason
        due = None
        if reason is not None:
            due = self.policy.cleanup_due_at_for(
                state=SandboxState.ORPHANED,
                terminal_reason=reason,
                reference_time=observation.observed_at,
            )
        return SandboxReconciliationPlan(
            classification=classification.classification,
            target_state=SandboxState.ORPHANED,
            target_cleanup_state=CleanupState.NONE,
            terminal_reason=reason,
            cleanup_due_at=due,
            action_required=False,
        )

    async def _require_record(self, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self.mutation_service.repository.get_record(sandbox_id)
        if record is None:
            raise SandboxLifecycleError(f"Sandbox lifecycle record not found: {sandbox_id}.")
        return record

    async def _publish_lost_runtime_control_plane_closure(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> None:
        if self.control_plane_publication is None:
            return
        publisher = SandboxControlPlaneReconciliationService(publication=self.control_plane_publication)
        published = await publisher.publish_lost_runtime_reconciliation(record=record, observed_at=observed_at)
        if self.control_plane_execution is not None and record.run_id is not None:
            await self.control_plane_execution.finalize_terminal_execution(
                run_id=record.run_id,
                observed_at=observed_at,
                terminal_reason=record.terminal_reason or TerminalReason.LOST_RUNTIME,
                policy_version=record.policy_version,
                final_truth_record_id=published.final_truth.final_truth_record_id if published.final_truth else None,
                rationale_ref=published.reconciliation_record.reconciliation_id,
                recovery_rationale_ref=published.reconciliation_record.reconciliation_id,
            )

    async def _publish_reconciliation_state_change(
        self,
        *,
        classification: ReconciliationClassification,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> None:
        if self.control_plane_publication is None:
            return
        publisher = SandboxControlPlaneReconciliationService(publication=self.control_plane_publication)
        if classification is ReconciliationClassification.RECLAIMABLE:
            await publisher.publish_reclaimable_reconciliation(record=record, observed_at=observed_at)
        elif classification is ReconciliationClassification.CLEANED_EXTERNALLY:
            await publisher.publish_cleaned_externally_reconciliation(record=record, observed_at=observed_at)

    async def _publish_resource_state_change(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> None:
        if self.control_plane_publication is None:
            return
        publisher = SandboxControlPlaneResourceService(publication=self.control_plane_publication)
        await publisher.publish_from_record(record=record, observed_at=observed_at)

    async def _publish_execution_waiting_on_resource(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> None:
        if self.control_plane_execution is None or record.run_id is None:
            return
        await self.control_plane_execution.mark_waiting_on_resource(
            run_id=record.run_id,
            observed_at=observed_at,
        )
        if self.control_plane_checkpoints is not None:
            await self.control_plane_checkpoints.publish_reclaimable_checkpoint(
                record=record,
                observed_at=observed_at,
            )

    @staticmethod
    def _is_due(deadline: str | None, observed_at: str) -> bool:
        if not deadline:
            return False
        return deadline <= observed_at
