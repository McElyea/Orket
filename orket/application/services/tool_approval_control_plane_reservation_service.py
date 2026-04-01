from __future__ import annotations

from collections.abc import Mapping

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.core.contracts import ReservationRecord
from orket.core.domain import ReservationKind, ReservationStatus


class ToolApprovalControlPlaneReservationService:
    """Publishes operator-hold reservations for supported pending-gate requests."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    @staticmethod
    def reservation_id(approval_id: str) -> str:
        normalized_id = str(approval_id or "").strip()
        if not normalized_id:
            raise ValueError("approval_id is required")
        return f"approval-reservation:{normalized_id}"

    async def publish_pending_tool_approval_hold(
        self,
        *,
        approval_id: str,
        session_id: str,
        issue_id: str,
        seat_name: str,
        tool_name: str,
        turn_index: int | None,
        created_at: str,
        control_plane_target_ref: str | None = None,
    ) -> ReservationRecord:
        approval_target_ref = ToolApprovalControlPlaneOperatorService.target_ref(approval_id)
        resolved_target_ref = str(control_plane_target_ref or "").strip()
        holder_ref = resolved_target_ref or approval_target_ref
        scope_tokens = [
            f"approval={approval_target_ref}",
            f"seat={str(seat_name).strip()}",
            f"tool={str(tool_name).strip()}",
        ]
        if turn_index is not None:
            scope_tokens.append(f"turn={int(turn_index):04d}")
        if str(session_id).strip():
            scope_tokens.append(f"session={str(session_id).strip()}")
        if str(issue_id).strip():
            scope_tokens.append(f"issue={str(issue_id).strip()}")
        if resolved_target_ref:
            scope_tokens.append(f"target={resolved_target_ref}")
        return await self.publication.publish_reservation(
            reservation_id=self.reservation_id(approval_id),
            holder_ref=holder_ref,
            reservation_kind=ReservationKind.OPERATOR_HOLD,
            target_scope_ref="operator-hold:" + ";".join(scope_tokens),
            creation_timestamp=created_at,
            expiry_or_invalidation_basis=f"pending_tool_approval:{str(tool_name).strip()}",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"tool-approval-gate:{approval_id}:create",
        )

    async def publish_pending_guard_review_hold(
        self,
        *,
        request_id: str,
        session_id: str,
        issue_id: str,
        seat_name: str,
        reason: str,
        gate_mode: str,
        created_at: str,
    ) -> ReservationRecord:
        request_target_ref = ToolApprovalControlPlaneOperatorService.target_ref(request_id)
        scope_tokens = [
            f"approval={request_target_ref}",
            f"seat={str(seat_name).strip()}",
            f"reason={str(reason).strip()}",
            "request_type=guard_rejection_payload",
        ]
        if str(gate_mode).strip():
            scope_tokens.append(f"gate_mode={str(gate_mode).strip()}")
        if str(session_id).strip():
            scope_tokens.append(f"session={str(session_id).strip()}")
        if str(issue_id).strip():
            scope_tokens.append(f"issue={str(issue_id).strip()}")
        return await self.publication.publish_reservation(
            reservation_id=self.reservation_id(request_id),
            holder_ref=request_target_ref,
            reservation_kind=ReservationKind.OPERATOR_HOLD,
            target_scope_ref="operator-hold:" + ";".join(scope_tokens),
            creation_timestamp=created_at,
            expiry_or_invalidation_basis=f"pending_guard_review:{str(reason).strip() or 'unknown'}",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref=f"guard-review-gate:{request_id}:create",
        )

    async def publish_resolved_pending_gate_hold(
        self,
        *,
        resolved_approval: Mapping[str, object],
    ) -> ReservationRecord | None:
        request_type = self._request_type_token(resolved_approval)
        if not self._is_supported_pending_gate(resolved_approval):
            return None
        approval_id = self._approval_id(resolved_approval)
        existing = await self.publication.repository.get_latest_reservation_record(
            reservation_id=self.reservation_id(approval_id)
        )
        if existing is None:
            return None
        status_token = self._status_token(resolved_approval)
        if status_token == "approved":
            return await self.publication.release_reservation(
                reservation_id=existing.reservation_id,
                supervisor_authority_ref=f"{request_type}-gate:{approval_id}:resolve",
                release_basis=self._release_basis(request_type=request_type, status_token=status_token),
            )
        if status_token == "denied":
            return await self.publication.invalidate_reservation(
                reservation_id=existing.reservation_id,
                supervisor_authority_ref=f"{request_type}-gate:{approval_id}:resolve",
                invalidation_basis=self._invalidation_basis(request_type=request_type),
            )
        raise ValueError("resolved approval must be approved or denied")

    async def publish_resolved_tool_approval_hold(
        self,
        *,
        resolved_approval: Mapping[str, object],
    ) -> ReservationRecord | None:
        if not self._is_tool_approval(resolved_approval):
            return None
        return await self.publish_resolved_pending_gate_hold(resolved_approval=resolved_approval)

    @staticmethod
    def _approval_id(approval: Mapping[str, object]) -> str:
        approval_id = str(approval.get("approval_id") or approval.get("request_id") or "").strip()
        if not approval_id:
            raise ValueError("approval_id is required")
        return approval_id

    @staticmethod
    def _status_token(approval: Mapping[str, object]) -> str:
        return str(approval.get("status") or "").strip().lower()

    @staticmethod
    def _is_tool_approval(approval: Mapping[str, object]) -> bool:
        request_type = str(approval.get("request_type") or "").strip().lower()
        reason = str(approval.get("reason") or "").strip().lower()
        reason_codes = approval.get("reason_codes")
        return (
            request_type == "tool_approval"
            or reason.startswith("approval_required_tool:")
            or isinstance(reason_codes, (list, tuple))
        )

    @staticmethod
    def _is_supported_pending_gate(approval: Mapping[str, object]) -> bool:
        request_type = ToolApprovalControlPlaneReservationService._request_type_token(approval)
        return request_type in {"tool_approval", "guard_rejection_payload"} or ToolApprovalControlPlaneReservationService._is_tool_approval(
            approval
        )

    @staticmethod
    def _request_type_token(approval: Mapping[str, object]) -> str:
        request_type = str(approval.get("request_type") or "").strip().lower()
        return request_type or "tool_approval"

    @staticmethod
    def _release_basis(*, request_type: str, status_token: str) -> str:
        if request_type == "tool_approval":
            return f"approval_resolved_continue:{status_token}"
        return f"pending_gate_resolved_continue:{request_type}:{status_token}"

    @staticmethod
    def _invalidation_basis(*, request_type: str) -> str:
        if request_type == "tool_approval":
            return "approval_denied_terminal_stop"
        return f"pending_gate_denied_terminal_stop:{request_type}"

__all__ = ["ToolApprovalControlPlaneReservationService"]
