from __future__ import annotations

from typing import Any

from orket.application.services.kernel_action_control_plane_resource_lifecycle import reservation_id_for_run
from orket.application.services.kernel_action_control_plane_support import (
    run_id_for as kernel_action_run_id_for,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)


class KernelAsyncControlPlaneService:
    """Owns async kernel control-plane publication and response augmentation for the engine."""

    def __init__(
        self,
        *,
        gateway_facade: Any,
        kernel_action_control_plane: Any,
        kernel_action_control_plane_operator: Any,
        kernel_action_control_plane_view: Any,
        control_plane_repository: Any,
        control_plane_publication: Any,
        get_approval: Any,
    ) -> None:
        self.gateway_facade = gateway_facade
        self.kernel_action_control_plane = kernel_action_control_plane
        self.kernel_action_control_plane_operator = kernel_action_control_plane_operator
        self.kernel_action_control_plane_view = kernel_action_control_plane_view
        self.control_plane_repository = control_plane_repository
        self.control_plane_publication = control_plane_publication
        self.get_approval = get_approval
        self._tool_approval_reservation = ToolApprovalControlPlaneReservationService(
            publication=control_plane_publication
        )

    async def _augment_kernel_response(
        self,
        *,
        response: dict[str, Any],
        session_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        view_service = self.kernel_action_control_plane_view
        if view_service is None:
            return response
        return dict(await view_service.augment_kernel_response(
            response=response,
            session_id=session_id,
            trace_id=trace_id,
        ))

    async def _publish_pending_kernel_approval_hold_if_needed(
        self,
        *,
        session_id: str,
        trace_id: str,
        proposal: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        admission_decision = response.get("admission_decision")
        if not isinstance(admission_decision, dict):
            return
        if str(admission_decision.get("decision") or "").strip() != "NEEDS_APPROVAL":
            return
        approval_id = str(response.get("approval_id") or "").strip()
        if not approval_id:
            return
        approval = await self.get_approval(approval_id)
        if not isinstance(approval, dict):
            return
        payload = proposal.get("payload")
        proposal_payload = payload if isinstance(payload, dict) else {}
        tool_name = str(proposal_payload.get("tool_name") or proposal.get("proposal_type") or "governed_action").strip()
        await self._tool_approval_reservation.publish_pending_tool_approval_hold(
            approval_id=approval_id,
            session_id=session_id,
            issue_id="",
            seat_name="kernel_action",
            tool_name=tool_name,
            turn_index=None,
            created_at=str(approval.get("created_at") or ""),
            control_plane_target_ref=kernel_action_run_id_for(session_id=session_id, trace_id=trace_id),
        )

    async def admit_proposal_async(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.gateway_facade.admit_proposal(request)
        ledger = self.gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 200,
            }
        )
        run, _attempt = await self.kernel_action_control_plane.record_admission(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        await self._publish_pending_kernel_approval_hold_if_needed(
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
            proposal=dict(request.get("proposal") or {}),
            response=response,
        )
        if self.kernel_action_control_plane_view is not None:
            return await self._augment_kernel_response(
                response=response,
                session_id=str(request.get("session_id") or ""),
                trace_id=str(request.get("trace_id") or ""),
            )
        reservation = await self.control_plane_repository.get_latest_reservation_record(
            reservation_id=reservation_id_for_run(run_id=run.run_id)
        )
        if reservation is not None:
            return {
                **response,
                "control_plane_run_id": run.run_id,
                "control_plane_reservation_id": reservation.reservation_id,
            }
        return response

    async def commit_proposal_async(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.gateway_facade.commit_proposal(request)
        ledger = self.gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 400,
            }
        )
        await self.kernel_action_control_plane.record_commit(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        return await self._augment_kernel_response(
            response=response,
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
        )

    async def end_session_async(self, request: dict[str, Any]) -> dict[str, Any]:
        response = self.gateway_facade.end_session(request)
        ledger = self.gateway_facade.list_ledger_events(
            {
                "contract_version": "kernel_api/v1",
                "session_id": request.get("session_id"),
                "trace_id": request.get("trace_id"),
                "limit": 200,
            }
        )
        closed = await self.kernel_action_control_plane.record_session_end(
            request=request,
            response=response,
            ledger_items=list(ledger.get("items") or []),
        )
        operator_actor_ref = str(request.get("operator_actor_ref") or "").strip()
        attestation_scope = str(request.get("attestation_scope") or "").strip()
        attestation_payload_raw = request.get("attestation_payload")
        attestation_payload = dict(attestation_payload_raw) if isinstance(attestation_payload_raw, dict) else {}
        if attestation_scope and not operator_actor_ref:
            raise ValueError(
                "kernel end-session attestation requires authenticated operator actor reference"
            )
        if closed is not None and operator_actor_ref:
            run, _attempt, _final_truth = closed
            session_end_timestamp = next(
                (
                    str(item.get("created_at") or "").strip()
                    for item in reversed(list(ledger.get("items") or []))
                    if str(item.get("event_type") or "") == "session.ended"
                ),
                "",
            )
            await self.kernel_action_control_plane_operator.publish_cancel_run_command(
                actor_ref=operator_actor_ref,
                session_id=str(request.get("session_id") or ""),
                trace_id=str(request.get("trace_id") or ""),
                timestamp=session_end_timestamp or str(run.creation_timestamp),
                receipt_ref=f"kernel-ledger-event:{response.get('event_digest')}",
                reason=str(request.get("reason") or "").strip() or None,
            )
            if attestation_scope:
                await self.kernel_action_control_plane_operator.publish_run_attestation(
                    actor_ref=operator_actor_ref,
                    session_id=str(request.get("session_id") or ""),
                    trace_id=str(request.get("trace_id") or ""),
                    timestamp=session_end_timestamp or str(run.creation_timestamp),
                    receipt_ref=f"kernel-ledger-event:{response.get('event_digest')}",
                    request_id=str(request.get("request_id") or "").strip() or None,
                    precondition_basis_ref=f"kernel-session-end:{str(request.get('reason') or '').strip() or 'unspecified'}",
                    attestation_scope=attestation_scope,
                    attestation_payload=attestation_payload,
                )
        return await self._augment_kernel_response(
            response=response,
            session_id=str(request.get("session_id") or ""),
            trace_id=str(request.get("trace_id") or ""),
        )
