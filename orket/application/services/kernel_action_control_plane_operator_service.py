from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.core.contracts import OperatorActionRecord
from orket.core.domain import OperatorCommandClass, OperatorInputClass


class KernelActionControlPlaneOperatorService:
    """Publishes operator command truth for governed kernel-action runs."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_cancel_run_command(
        self,
        *,
        actor_ref: str,
        session_id: str,
        trace_id: str,
        timestamp: str,
        receipt_ref: str,
        reason: str | None = None,
    ) -> OperatorActionRecord:
        run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
        return await self.publication.publish_operator_action(
            action_id=f"kernel-action-operator:{session_id}:{trace_id}:cancel",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.COMMAND,
            target_ref=run_id,
            timestamp=timestamp,
            precondition_basis_ref=f"kernel-session-end:{reason or 'unspecified'}",
            result="accepted_cancel",
            command_class=OperatorCommandClass.CANCEL_RUN,
            affected_transition_refs=[run_id],
            receipt_refs=[receipt_ref],
        )

    async def publish_run_attestation(
        self,
        *,
        actor_ref: str,
        session_id: str,
        trace_id: str,
        timestamp: str,
        receipt_ref: str,
        attestation_scope: str,
        attestation_payload: dict[str, object] | None = None,
        precondition_basis_ref: str | None = None,
        request_id: str | None = None,
    ) -> OperatorActionRecord:
        run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
        scope = str(attestation_scope or "").strip()
        if not scope:
            raise ValueError("kernel-action operator attestation requires non-empty attestation_scope")
        action_suffix = str(request_id or receipt_ref or timestamp).strip() or "recorded"
        return await self.publication.publish_operator_action(
            action_id=f"kernel-action-operator:{session_id}:{trace_id}:run-attestation:{action_suffix}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.ATTESTATION,
            target_ref=run_id,
            timestamp=timestamp,
            precondition_basis_ref=precondition_basis_ref or "kernel-session-end:operator_attestation",
            result="recorded_attestation",
            attestation_scope=scope,
            attestation_payload=dict(attestation_payload or {}),
            affected_transition_refs=[run_id],
            receipt_refs=[receipt_ref],
        )


__all__ = ["KernelActionControlPlaneOperatorService"]
