from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.application.services.kernel_action_control_plane_support import run_id_for as kernel_action_run_id_for
from orket.interfaces.routers.approvals import build_approvals_router


class KernelLifecycleRequest(BaseModel):
    workflow_id: str
    execute_turn_requests: List[dict[str, Any]]
    finish_outcome: str = "PASS"
    start_request: Optional[dict[str, Any]] = None


class KernelCompareRequest(BaseModel):
    run_a: dict[str, Any]
    run_b: dict[str, Any]
    compare_mode: str = "structural_parity"


class KernelReplayRequest(BaseModel):
    run_descriptor: dict[str, Any]


class KernelProjectionPackRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: Optional[str] = None
    purpose: str = "action_path"
    canonical_state_digest: Optional[str] = None
    tool_context_summary: dict[str, Any] = Field(default_factory=dict)
    policy_context: dict[str, Any] = Field(default_factory=dict)


class KernelAdmitProposalRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: Optional[str] = None
    proposal: dict[str, Any]


class KernelCommitProposalRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: Optional[str] = None
    proposal_digest: str
    admission_decision_digest: str
    approval_id: Optional[str] = None
    execution_result_digest: Optional[str] = None
    execution_result_payload: Any = None
    execution_result_schema_valid: Optional[bool] = None
    execution_error_reason_code: Optional[str] = None
    sanitization_digest: Optional[str] = None
    revalidate_policy_forbidden: bool = False
    canonical_state_digest_after: Optional[str] = None
    block_result_leaks: bool = False


class KernelEndSessionRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: Optional[str] = None
    reason: Optional[str] = None
    attestation_scope: Optional[str] = None
    attestation_payload: dict[str, Any] = Field(default_factory=dict)


class KernelRebuildPendingApprovalsRequest(BaseModel):
    session_id: str


def build_kernel_router(engine_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    async def _augment_kernel_response_with_control_plane_refs(
        *,
        engine: Any,
        response: dict[str, Any],
        session_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        view_service = getattr(engine, "kernel_action_control_plane_view", None)
        if view_service is None:
            return response
        summary = await view_service.build_summary(session_id=session_id, trace_id=trace_id)
        if summary is None:
            return response
        augmented = dict(response)
        augmented["control_plane_run_id"] = summary.get("run_id")
        augmented["control_plane_attempt_id"] = summary.get("current_attempt_id")
        augmented["control_plane_attempt_state"] = summary.get("current_attempt_state")
        reservation = summary.get("latest_reservation")
        if isinstance(reservation, dict):
            augmented["control_plane_reservation_id"] = reservation.get("reservation_id")
        lease = summary.get("latest_lease")
        if isinstance(lease, dict):
            augmented["control_plane_lease_id"] = lease.get("lease_id")
        final_truth = summary.get("final_truth")
        if isinstance(final_truth, dict):
            augmented["control_plane_final_truth_record_id"] = final_truth.get("final_truth_record_id")
        if summary.get("current_recovery_decision_id") is not None:
            augmented["control_plane_recovery_decision_id"] = summary.get("current_recovery_decision_id")
        if summary.get("current_recovery_action") is not None:
            augmented["control_plane_recovery_action"] = summary.get("current_recovery_action")
        operator_action = summary.get("latest_operator_action")
        if isinstance(operator_action, dict):
            augmented["control_plane_operator_action_id"] = operator_action.get("action_id")
        return augmented

    @router.post("/kernel/lifecycle")
    async def kernel_lifecycle(req: KernelLifecycleRequest):
        engine = engine_getter()
        return engine.kernel_run_lifecycle(
            workflow_id=req.workflow_id,
            execute_turn_requests=req.execute_turn_requests,
            finish_outcome=req.finish_outcome,
            start_request=req.start_request,
        )

    @router.post("/kernel/compare")
    async def kernel_compare(req: KernelCompareRequest):
        engine = engine_getter()
        return engine.kernel_compare_runs(
            {
                "contract_version": "kernel_api/v1",
                "run_a": req.run_a,
                "run_b": req.run_b,
                "compare_mode": req.compare_mode,
            }
        )

    @router.post("/kernel/replay")
    async def kernel_replay(req: KernelReplayRequest):
        engine = engine_getter()
        return engine.kernel_replay_run(
            {
                "contract_version": "kernel_api/v1",
                "run_descriptor": req.run_descriptor,
            }
        )

    @router.post("/kernel/projection-pack")
    async def kernel_projection_pack(req: KernelProjectionPackRequest):
        engine = engine_getter()
        try:
            return engine.kernel_projection_pack(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": req.session_id,
                    "trace_id": req.trace_id,
                    "request_id": req.request_id,
                    "purpose": req.purpose,
                    "canonical_state_digest": req.canonical_state_digest,
                    "tool_context_summary": req.tool_context_summary,
                    "policy_context": req.policy_context,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/kernel/admit-proposal")
    async def kernel_admit_proposal(req: KernelAdmitProposalRequest):
        engine = engine_getter()
        try:
            handler = getattr(engine, "kernel_admit_proposal_async", None)
            payload = {
                "contract_version": "kernel_api/v1",
                "session_id": req.session_id,
                "trace_id": req.trace_id,
                "request_id": req.request_id,
                "proposal": req.proposal,
            }
            if callable(handler):
                response = await handler(payload)
            else:
                response = engine.kernel_admit_proposal(
                    {
                        **payload,
                    }
                )
            await _publish_kernel_approval_reservation_if_needed(
                engine=engine,
                session_id=req.session_id,
                trace_id=req.trace_id,
                proposal=req.proposal,
                response=response,
            )
            return await _augment_kernel_response_with_control_plane_refs(
                engine=engine,
                response=response,
                session_id=req.session_id,
                trace_id=req.trace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def _publish_kernel_approval_reservation_if_needed(
        *,
        engine: Any,
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
        publication = getattr(engine, "control_plane_publication", None)
        if publication is None:
            return
        approval = await engine.get_approval(approval_id)
        if not isinstance(approval, dict):
            return
        payload = proposal.get("payload")
        proposal_payload = payload if isinstance(payload, dict) else {}
        tool_name = str(proposal_payload.get("tool_name") or proposal.get("proposal_type") or "governed_action").strip()
        publisher = getattr(engine, "tool_approval_control_plane_reservation", None)
        if publisher is None or getattr(publisher, "publication", None) is not publication:
            publisher = ToolApprovalControlPlaneReservationService(publication=publication)
            setattr(engine, "tool_approval_control_plane_reservation", publisher)
        await publisher.publish_pending_tool_approval_hold(
            approval_id=approval_id,
            session_id=session_id,
            issue_id="",
            seat_name="kernel_action",
            tool_name=tool_name,
            turn_index=None,
            created_at=str(approval.get("created_at") or ""),
            control_plane_target_ref=kernel_action_run_id_for(session_id=session_id, trace_id=trace_id),
        )

    @router.post("/kernel/commit-proposal")
    async def kernel_commit_proposal(req: KernelCommitProposalRequest):
        engine = engine_getter()
        try:
            handler = getattr(engine, "kernel_commit_proposal_async", None)
            payload = {
                "contract_version": "kernel_api/v1",
                "session_id": req.session_id,
                "trace_id": req.trace_id,
                "request_id": req.request_id,
                "proposal_digest": req.proposal_digest,
                "admission_decision_digest": req.admission_decision_digest,
                "approval_id": req.approval_id,
                "execution_result_digest": req.execution_result_digest,
                "execution_result_payload": req.execution_result_payload,
                "execution_result_schema_valid": req.execution_result_schema_valid,
                "execution_error_reason_code": req.execution_error_reason_code,
                "sanitization_digest": req.sanitization_digest,
                "revalidate_policy_forbidden": req.revalidate_policy_forbidden,
                "canonical_state_digest_after": req.canonical_state_digest_after,
                "block_result_leaks": req.block_result_leaks,
            }
            if callable(handler):
                response = await handler(payload)
            else:
                response = engine.kernel_commit_proposal(
                    {
                        **payload,
                    }
                )
            return await _augment_kernel_response_with_control_plane_refs(
                engine=engine,
                response=response,
                session_id=req.session_id,
                trace_id=req.trace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/kernel/end-session")
    async def kernel_end_session(req: KernelEndSessionRequest, request: Request):
        engine = engine_getter()
        try:
            handler = getattr(engine, "kernel_end_session_async", None)
            payload = {
                "contract_version": "kernel_api/v1",
                "session_id": req.session_id,
                "trace_id": req.trace_id,
                "request_id": req.request_id,
                "reason": req.reason,
                "attestation_scope": req.attestation_scope,
                "attestation_payload": req.attestation_payload,
                "operator_actor_ref": getattr(request.state, "authenticated_actor_ref", None),
            }
            if callable(handler):
                response = await handler(payload)
            else:
                response = engine.kernel_end_session(
                    {
                        **payload,
                    }
                )
            return await _augment_kernel_response_with_control_plane_refs(
                engine=engine,
                response=response,
                session_id=req.session_id,
                trace_id=req.trace_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/kernel/ledger-events")
    async def kernel_list_ledger_events(
        session_id: str,
        trace_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 200,
    ):
        engine = engine_getter()
        try:
            return engine.kernel_list_ledger_events(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "event_type": event_type,
                    "limit": limit,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/kernel/approvals/rebuild")
    async def kernel_rebuild_pending_approvals(req: KernelRebuildPendingApprovalsRequest):
        engine = engine_getter()
        try:
            return engine.kernel_rebuild_pending_approvals(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": req.session_id,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/kernel/action-lifecycle/replay")
    async def kernel_replay_action_lifecycle(session_id: str, trace_id: str):
        engine = engine_getter()
        try:
            payload = {
                "contract_version": "kernel_api/v1",
                "session_id": session_id,
                "trace_id": trace_id,
            }
            response = engine.kernel_replay_action_lifecycle(
                {
                    **payload,
                }
            )
            view_service = getattr(engine, "kernel_action_control_plane_view", None)
            if view_service is not None:
                response["control_plane"] = await view_service.build_summary(
                    session_id=session_id,
                    trace_id=trace_id,
                )
            return response
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/kernel/action-lifecycle/audit")
    async def kernel_audit_action_lifecycle(session_id: str, trace_id: str):
        engine = engine_getter()
        try:
            response = engine.kernel_audit_action_lifecycle(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": session_id,
                    "trace_id": trace_id,
                }
            )
            view_service = getattr(engine, "kernel_action_control_plane_view", None)
            if view_service is not None:
                response["control_plane"] = await view_service.build_summary(
                    session_id=session_id,
                    trace_id=trace_id,
                )
            return response
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    router.include_router(build_approvals_router(engine_getter))

    return router
