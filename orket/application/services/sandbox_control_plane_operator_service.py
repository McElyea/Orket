from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import FinalTruthRecord, OperatorActionRecord
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


class SandboxControlPlaneOperatorService:
    """Publishes explicit sandbox operator commands into the control-plane store."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_cancel_run_action(
        self,
        *,
        actor_ref: str,
        before_record: SandboxLifecycleRecord,
        after_record: SandboxLifecycleRecord,
        final_truth: FinalTruthRecord | None = None,
    ) -> OperatorActionRecord:
        timestamp = (
            after_record.terminal_at
            or after_record.last_heartbeat_at
            or before_record.last_heartbeat_at
            or before_record.created_at
        )
        target_ref = before_record.run_id or f"sandbox:{before_record.sandbox_id}"
        transition_ref = (
            f"sandbox-lifecycle:{before_record.sandbox_id}:"
            f"{before_record.state.value}->{after_record.state.value}:{after_record.record_version}"
        )
        receipt_refs = []
        if after_record.required_evidence_ref:
            receipt_refs.append(after_record.required_evidence_ref)
        if final_truth is not None:
            receipt_refs.append(final_truth.final_truth_record_id)
        return await self.publication.publish_operator_action(
            action_id=f"sandbox-operator-action:{before_record.sandbox_id}:cancel_run:{timestamp}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.COMMAND,
            target_ref=target_ref,
            timestamp=timestamp,
            precondition_basis_ref=(
                f"sandbox-lifecycle:{before_record.sandbox_id}:"
                f"{before_record.state.value}:{before_record.record_version}"
            ),
            result="accepted",
            command_class=OperatorCommandClass.CANCEL_RUN,
            affected_transition_refs=[transition_ref],
            affected_resource_refs=[
                f"sandbox-runtime:{before_record.sandbox_id}",
                f"sandbox-lease:{before_record.sandbox_id}",
            ],
            receipt_refs=receipt_refs,
        )


__all__ = ["SandboxControlPlaneOperatorService"]
