from __future__ import annotations

from collections.abc import Mapping

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.core.contracts import OperatorActionRecord
from orket.core.domain import OperatorCommandClass, OperatorInputClass


class PendingGateControlPlaneOperatorService:
    """Publishes operator commands for supported non-tool pending-gate resolutions."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def supports_resolution(approval: Mapping[str, object]) -> bool:
        request_type = str(approval.get("request_type") or "").strip().lower()
        return request_type == "guard_rejection_payload"

    async def publish_resolution_operator_action(
        self,
        *,
        actor_ref: str,
        previous_approval: Mapping[str, object] | None,
        resolved_approval: Mapping[str, object],
    ) -> OperatorActionRecord:
        if not self.supports_resolution(resolved_approval):
            raise ValueError("resolved approval is not a supported non-tool pending gate")

        approval_id = self._approval_id(resolved_approval)
        status_token = self._status_token(resolved_approval)
        if status_token not in {"approved", "denied"}:
            raise ValueError("resolved approval must be approved or denied")

        before_status = self._status_token(previous_approval)
        timestamp = self._timestamp(resolved_approval)
        target_ref = ToolApprovalControlPlaneOperatorService.target_ref(approval_id)
        affected_resource_refs: list[str] = []
        session_id = str(resolved_approval.get("session_id") or "").strip()
        issue_id = str(resolved_approval.get("issue_id") or "").strip()
        if session_id:
            affected_resource_refs.append(f"session:{session_id}")
        if issue_id:
            affected_resource_refs.append(f"issue:{issue_id}")

        command_class = (
            OperatorCommandClass.APPROVE_CONTINUE
            if status_token == "approved"
            else OperatorCommandClass.MARK_TERMINAL
        )
        return await self.publication.publish_operator_action(
            action_id=f"pending-gate-operator-action:{approval_id}:{status_token}:{timestamp}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.COMMAND,
            target_ref=target_ref,
            timestamp=timestamp,
            precondition_basis_ref=f"{target_ref}:status:{before_status}",
            result=status_token,
            command_class=command_class,
            affected_transition_refs=[f"{target_ref}:{before_status}->{status_token}"],
            affected_resource_refs=affected_resource_refs,
        )

    @staticmethod
    def _approval_id(approval: Mapping[str, object]) -> str:
        approval_id = str(approval.get("approval_id") or approval.get("request_id") or "").strip()
        if not approval_id:
            raise ValueError("approval_id is required")
        return approval_id

    @staticmethod
    def _status_token(approval: Mapping[str, object] | None) -> str:
        if approval is None:
            return "pending"
        return str(approval.get("status") or "PENDING").strip().lower()

    @staticmethod
    def _timestamp(approval: Mapping[str, object]) -> str:
        for field in ("resolved_at", "updated_at", "created_at"):
            token = str(approval.get(field) or "").strip()
            if token:
                return token
        raise ValueError("resolved approval is missing a publication timestamp")


__all__ = ["PendingGateControlPlaneOperatorService"]
