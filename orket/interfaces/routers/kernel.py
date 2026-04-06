from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orket.application.services.kernel_action_pending_approval_reservation import (
    publish_pending_kernel_approval_hold_if_needed,
)
from orket.interfaces.routers.approvals import build_approvals_router


class KernelLifecycleRequest(BaseModel):
    workflow_id: str
    execute_turn_requests: list[dict[str, Any]]
    finish_outcome: str = "PASS"
    start_request: dict[str, Any] | None = None


class KernelCompareRequest(BaseModel):
    run_a: dict[str, Any]
    run_b: dict[str, Any]
    compare_mode: str = "structural_parity"


class KernelReplayRequest(BaseModel):
    run_descriptor: dict[str, Any]


class KernelProjectionPackRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: str | None = None
    purpose: str = "action_path"
    canonical_state_digest: str | None = None
    tool_context_summary: dict[str, Any] = Field(default_factory=dict)
    policy_context: dict[str, Any] = Field(default_factory=dict)


class KernelAdmitProposalRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: str | None = None
    proposal: dict[str, Any]


class KernelCommitProposalRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: str | None = None
    proposal_digest: str
    admission_decision_digest: str
    approval_id: str | None = None
    execution_result_digest: str | None = None
    execution_result_payload: Any = None
    execution_result_schema_valid: bool | None = None
    execution_error_reason_code: str | None = None
    sanitization_digest: str | None = None
    revalidate_policy_forbidden: bool = False
    canonical_state_digest_after: str | None = None
    block_result_leaks: bool = False


class KernelEndSessionRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: str | None = None
    reason: str | None = None
    attestation_scope: str | None = None
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
        return await view_service.augment_kernel_response(
            response=response,
            session_id=session_id,
            trace_id=trace_id,
        )

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
                return await handler(payload)
            response = engine.kernel_admit_proposal(
                {
                    **payload,
                }
            )
            await publish_pending_kernel_approval_hold_if_needed(
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
                return await handler(payload)
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
                return await handler(payload)
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
        trace_id: str | None = None,
        event_type: str | None = None,
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
