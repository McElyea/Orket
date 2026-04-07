from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_target_resource_refs import resource_id_for_supported_run
from orket.core.contracts import OperatorActionRecord
from orket.core.contracts.control_plane_models import RunRecord
from orket.core.domain import OperatorCommandClass, OperatorInputClass


class ExecutionRepository(Protocol):
    async def get_run_record(self, *, run_id: str) -> RunRecord | None: ...


class ToolApprovalControlPlaneOperatorService:
    """Publishes approval resolutions as control-plane risk acceptance or terminal commands."""

    def __init__(
        self,
        *,
        publication: ControlPlanePublicationService,
        execution_repository: ExecutionRepository | None = None,
    ) -> None:
        self.publication = publication
        self.execution_repository = execution_repository

    @staticmethod
    def target_ref(approval_id: str) -> str:
        normalized_id = str(approval_id or "").strip()
        if not normalized_id:
            raise ValueError("approval_id is required")
        return f"approval-request:{normalized_id}"

    async def publish_granted_approval_risk_acceptance(
        self,
        *,
        actor_ref: str,
        previous_approval: Mapping[str, object] | None,
        resolved_approval: Mapping[str, object],
    ) -> OperatorActionRecord:
        action = await self.publish_resolution_operator_action(
            actor_ref=actor_ref,
            previous_approval=previous_approval,
            resolved_approval=resolved_approval,
        )
        if action.input_class is not OperatorInputClass.RISK_ACCEPTANCE:
            raise ValueError("resolved approval did not publish risk acceptance")
        return action

    async def publish_resolution_operator_action(
        self,
        *,
        actor_ref: str,
        previous_approval: Mapping[str, object] | None,
        resolved_approval: Mapping[str, object],
    ) -> OperatorActionRecord:
        if not self.supports_resolution(resolved_approval):
            raise ValueError("resolved approval is not a supported tool approval row")
        approval_id = self._approval_id(resolved_approval)
        status_token = self._status_token(resolved_approval)
        if status_token not in {"approved", "denied"}:
            raise ValueError("resolved approval must be approved or denied")

        resolution = self._mapping_or_empty(resolved_approval.get("resolution"))
        payload = self._mapping_or_empty(resolved_approval.get("payload"))
        raw_decision_token = str(resolution.get("decision") or "").strip().lower()
        decision_token = "deny" if status_token == "denied" else raw_decision_token or "approve"
        action_namespace = "deny" if status_token == "denied" else "approve"
        before_status = self._status_token(previous_approval)
        timestamp = self._timestamp(resolved_approval)
        session_id = str(resolved_approval.get("session_id") or "").strip()
        issue_id = str(resolved_approval.get("issue_id") or "").strip()
        gate_mode = str(resolved_approval.get("gate_mode") or "").strip()
        request_type = str(resolved_approval.get("request_type") or "").strip()
        reason = str(resolved_approval.get("reason") or "").strip()
        control_plane_target_ref = str(payload.get("control_plane_target_ref") or "").strip()
        if not control_plane_target_ref:
            control_plane_target_ref = await self._target_ref_from_reservation(approval_id=approval_id)

        affected_resource_refs = []
        if session_id:
            affected_resource_refs.append(f"session:{session_id}")
        if issue_id:
            affected_resource_refs.append(f"issue:{issue_id}")
        for resource_ref in await self._target_resource_refs(control_plane_target_ref=control_plane_target_ref):
            if resource_ref not in affected_resource_refs:
                affected_resource_refs.append(resource_ref)

        if status_token == "denied":
            action = await self.publication.publish_operator_action(
                action_id=f"approval-operator-action:{approval_id}:{action_namespace}:{decision_token}:{timestamp}",
                actor_ref=actor_ref,
                input_class=OperatorInputClass.COMMAND,
                target_ref=self.target_ref(approval_id),
                timestamp=timestamp,
                precondition_basis_ref=f"{self.target_ref(approval_id)}:status:{before_status}",
                result=status_token,
                command_class=OperatorCommandClass.MARK_TERMINAL,
                affected_transition_refs=[
                    f"{self.target_ref(approval_id)}:{before_status}->{status_token}",
                ],
                affected_resource_refs=affected_resource_refs,
            )
            await self._publish_targeted_run_action_if_present(
                actor_ref=actor_ref,
                approval_id=approval_id,
                before_status=before_status,
                status_token=status_token,
                decision_token=decision_token,
                timestamp=timestamp,
                control_plane_target_ref=control_plane_target_ref,
                affected_resource_refs=affected_resource_refs,
            )
            return action

        scope_tokens = [
            "tool_approval",
            f"decision={decision_token}",
            f"status={status_token}",
        ]
        if gate_mode:
            scope_tokens.append(f"gate_mode={gate_mode}")
        if request_type:
            scope_tokens.append(f"request_type={request_type}")
        if reason:
            scope_tokens.append(f"reason={reason}")
        if session_id:
            scope_tokens.append(f"session_id={session_id}")
        if issue_id:
            scope_tokens.append(f"issue_id={issue_id}")

        action = await self.publication.publish_operator_action(
            action_id=f"approval-operator-action:{approval_id}:{action_namespace}:{decision_token}:{timestamp}",
            actor_ref=actor_ref,
            input_class=OperatorInputClass.RISK_ACCEPTANCE,
            target_ref=self.target_ref(approval_id),
            timestamp=timestamp,
            precondition_basis_ref=f"{self.target_ref(approval_id)}:status:{before_status}",
            result=status_token,
            risk_acceptance_scope=";".join(scope_tokens),
            affected_transition_refs=[
                f"{self.target_ref(approval_id)}:{before_status}->{status_token}",
            ],
            affected_resource_refs=affected_resource_refs,
        )
        await self._publish_targeted_run_action_if_present(
            actor_ref=actor_ref,
            approval_id=approval_id,
            before_status=before_status,
            status_token=status_token,
            decision_token=decision_token,
            timestamp=timestamp,
            control_plane_target_ref=control_plane_target_ref,
            affected_resource_refs=affected_resource_refs,
            risk_acceptance_scope=";".join(scope_tokens),
        )
        return action

    async def _publish_targeted_run_action_if_present(
        self,
        *,
        actor_ref: str,
        approval_id: str,
        before_status: str,
        status_token: str,
        decision_token: str,
        timestamp: str,
        control_plane_target_ref: str,
        affected_resource_refs: list[str],
        risk_acceptance_scope: str | None = None,
    ) -> OperatorActionRecord | None:
        if not control_plane_target_ref:
            return None
        action_namespace = "deny" if status_token == "denied" else "approve"
        action_id = f"approval-run-operator-action:{approval_id}:{action_namespace}:{decision_token}:{timestamp}"
        precondition_basis_ref = f"{self.target_ref(approval_id)}:status:{before_status}"
        if status_token == "denied":
            return await self.publication.publish_operator_action(
                action_id=action_id,
                actor_ref=actor_ref,
                input_class=OperatorInputClass.COMMAND,
                target_ref=control_plane_target_ref,
                timestamp=timestamp,
                precondition_basis_ref=precondition_basis_ref,
                result=status_token,
                command_class=OperatorCommandClass.MARK_TERMINAL,
                affected_transition_refs=[
                    f"{control_plane_target_ref}:approval:{before_status}->{status_token}",
                ],
                affected_resource_refs=[*affected_resource_refs, control_plane_target_ref],
                receipt_refs=[self.target_ref(approval_id)],
            )
        return await self.publication.publish_operator_action(
            action_id=action_id,
            actor_ref=actor_ref,
            input_class=OperatorInputClass.RISK_ACCEPTANCE,
            target_ref=control_plane_target_ref,
            timestamp=timestamp,
            precondition_basis_ref=precondition_basis_ref,
            result=status_token,
            risk_acceptance_scope=str(risk_acceptance_scope or "").strip() or "tool_approval",
            affected_transition_refs=[
                f"{control_plane_target_ref}:approval:{before_status}->{status_token}",
            ],
            affected_resource_refs=[*affected_resource_refs, control_plane_target_ref],
            receipt_refs=[self.target_ref(approval_id)],
        )

    async def _target_ref_from_reservation(self, *, approval_id: str) -> str:
        reservation = await self.publication.repository.get_latest_reservation_record(
            reservation_id=f"approval-reservation:{approval_id}"
        )
        if reservation is None:
            return ""
        holder_ref = str(reservation.holder_ref or "").strip()
        if holder_ref == self.target_ref(approval_id):
            return ""
        return holder_ref

    async def _target_resource_refs(self, *, control_plane_target_ref: str) -> list[str]:
        execution_repository = self.execution_repository
        target_ref = str(control_plane_target_ref or "").strip()
        if not target_ref:
            return []
        if execution_repository is None:
            raise ValueError("execution_repository is required when control_plane_target_ref is present")
        run = await execution_repository.get_run_record(run_id=target_ref)
        if run is None:
            return []
        resource_id = resource_id_for_supported_run(run=run)
        if not resource_id:
            return []
        return [resource_id]

    @staticmethod
    def _mapping_or_empty(value: object) -> Mapping[str, object]:
        return value if isinstance(value, Mapping) else {}

    def _approval_id(self, approval: Mapping[str, object]) -> str:
        approval_id = str(approval.get("approval_id") or approval.get("request_id") or "").strip()
        if not approval_id:
            raise ValueError("approval_id is required")
        return approval_id

    def _status_token(self, approval: Mapping[str, object] | None) -> str:
        if approval is None:
            return "pending"
        return str(approval.get("status") or "PENDING").strip().lower()

    @staticmethod
    def supports_resolution(approval: Mapping[str, object]) -> bool:
        request_type = str(approval.get("request_type") or "").strip().lower()
        reason = str(approval.get("reason") or "").strip().lower()
        reason_codes = approval.get("reason_codes")
        return (
            request_type == "tool_approval"
            or reason.startswith("approval_required_tool:")
            or isinstance(reason_codes, (list, tuple))
        )

    @staticmethod
    def _timestamp(approval: Mapping[str, object]) -> str:
        for field in ("resolved_at", "updated_at", "created_at"):
            token = str(approval.get(field) or "").strip()
            if token:
                return token
        raise ValueError("resolved approval is missing a publication timestamp")


__all__ = ["ToolApprovalControlPlaneOperatorService"]
