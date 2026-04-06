from __future__ import annotations

from typing import TYPE_CHECKING

from orket.application.services.sandbox_control_plane_closure_service import SandboxControlPlaneClosureService
from orket.core.domain.sandbox_lifecycle import LifecycleEvent, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord

if TYPE_CHECKING:
    from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService


class SandboxTerminalOutcomeService:
    """Exports terminal evidence before recording durable terminal outcomes."""

    def __init__(self, *, lifecycle_service: SandboxRuntimeLifecycleService) -> None:
        self.lifecycle_service = lifecycle_service

    async def record_workflow_terminal_outcome(
        self,
        *,
        sandbox_id: str,
        terminal_reason: TerminalReason,
        evidence_payload: dict[str, object],
        operation_id_prefix: str,
        expected_owner_instance_id: str | None = None,
        expected_lease_epoch: int | None = None,
        terminal_at: str | None = None,
        cleanup_due_at: str | None = None,
    ) -> SandboxLifecycleRecord:
        return await self._record_terminal_outcome(
            sandbox_id=sandbox_id,
            event=LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME,
            terminal_reason=terminal_reason,
            evidence_payload=evidence_payload,
            operation_id_prefix=operation_id_prefix,
            event_type="sandbox.workflow_terminal_outcome",
            expected_owner_instance_id=expected_owner_instance_id,
            expected_lease_epoch=expected_lease_epoch,
            terminal_at=terminal_at,
            cleanup_due_at=cleanup_due_at,
        )

    async def record_policy_terminal_outcome(
        self,
        *,
        sandbox_id: str,
        event: LifecycleEvent,
        terminal_reason: TerminalReason,
        evidence_payload: dict[str, object],
        operation_id_prefix: str,
        expected_owner_instance_id: str | None = None,
        expected_lease_epoch: int | None = None,
        terminal_at: str | None = None,
        cleanup_due_at: str | None = None,
    ) -> SandboxLifecycleRecord:
        return await self._record_terminal_outcome(
            sandbox_id=sandbox_id,
            event=event,
            terminal_reason=terminal_reason,
            evidence_payload=evidence_payload,
            operation_id_prefix=operation_id_prefix,
            event_type="sandbox.policy_terminal_outcome",
            expected_owner_instance_id=expected_owner_instance_id,
            expected_lease_epoch=expected_lease_epoch,
            terminal_at=terminal_at,
            cleanup_due_at=cleanup_due_at,
        )

    async def record_lifecycle_terminal_outcome(
        self,
        *,
        sandbox_id: str,
        event: LifecycleEvent,
        terminal_reason: TerminalReason,
        evidence_payload: dict[str, object],
        operation_id_prefix: str,
        expected_owner_instance_id: str | None = None,
        expected_lease_epoch: int | None = None,
        terminal_at: str | None = None,
        cleanup_due_at: str | None = None,
    ) -> SandboxLifecycleRecord:
        return await self._record_terminal_outcome(
            sandbox_id=sandbox_id,
            event=event,
            terminal_reason=terminal_reason,
            evidence_payload=evidence_payload,
            operation_id_prefix=operation_id_prefix,
            event_type="sandbox.lifecycle_terminal_outcome",
            expected_owner_instance_id=expected_owner_instance_id,
            expected_lease_epoch=expected_lease_epoch,
            terminal_at=terminal_at,
            cleanup_due_at=cleanup_due_at,
        )

    async def _record_terminal_outcome(
        self,
        *,
        sandbox_id: str,
        event: LifecycleEvent,
        terminal_reason: TerminalReason,
        evidence_payload: dict[str, object],
        operation_id_prefix: str,
        event_type: str,
        expected_owner_instance_id: str | None,
        expected_lease_epoch: int | None,
        terminal_at: str | None,
        cleanup_due_at: str | None,
    ) -> SandboxLifecycleRecord:
        current = await self.lifecycle_service._require_record(sandbox_id)
        observed_at = terminal_at or self.lifecycle_service._now()
        due_at = cleanup_due_at or self.lifecycle_service.policy.cleanup_due_at_for(
            state=SandboxState.TERMINAL,
            terminal_reason=terminal_reason,
            reference_time=observed_at,
        )
        evidence_ref = await self.lifecycle_service.terminal_evidence.export(
            sandbox_id=sandbox_id,
            terminal_reason=terminal_reason,
            created_at=observed_at,
            payload=evidence_payload,
        )
        current = await self.lifecycle_service._apply_record_copy(
            record=current,
            operation_id=f"{operation_id_prefix}:evidence:{sandbox_id}:{current.record_version}",
            updates={"required_evidence_ref": evidence_ref},
        )
        terminal = (
            await self.lifecycle_service.mutations.transition_state(
                sandbox_id=sandbox_id,
                operation_id=f"{operation_id_prefix}:terminal:{sandbox_id}:{current.record_version}",
                expected_record_version=current.record_version,
                event=event,
                next_state=SandboxState.TERMINAL,
                terminal_reason=terminal_reason,
                expected_owner_instance_id=expected_owner_instance_id,
                expected_lease_epoch=expected_lease_epoch,
                terminal_at=observed_at,
                cleanup_due_at=due_at,
            )
        ).record
        await self.lifecycle_service._publish_control_plane_resource(record=terminal, observed_at=observed_at)
        publication = self.lifecycle_service.control_plane_publication
        final_truth = None
        if publication is not None:
            closure = SandboxControlPlaneClosureService(publication=publication)
            final_truth = await closure.publish_terminal_final_truth(record=terminal)
        if self.lifecycle_service.control_plane_execution is not None and terminal.run_id is not None:
            await self.lifecycle_service.control_plane_execution.finalize_terminal_execution(
                run_id=terminal.run_id,
                observed_at=observed_at,
                terminal_reason=terminal.terminal_reason or terminal_reason,
                policy_version=terminal.policy_version,
                final_truth_record_id=None if final_truth is None else final_truth.final_truth_record_id,
                rationale_ref=evidence_ref,
            )
        await self.lifecycle_service.event_publisher.emit(
            sandbox_id=sandbox_id,
            created_at=observed_at,
            event_type=event_type,
            payload={
                "reason_code": terminal_reason.value,
                "required_evidence_ref": evidence_ref,
                "terminal_at": observed_at,
                "cleanup_due_at": due_at,
                "state": terminal.state.value,
                "cleanup_state": terminal.cleanup_state.value,
            },
        )
        return terminal
