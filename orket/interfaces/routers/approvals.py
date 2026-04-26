from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel


class ApprovalDecisionRequest(BaseModel):
    decision: str
    edited_proposal: dict[str, Any] | None = None
    notes: str | None = None


class OutwardApprovalDenyRequest(BaseModel):
    reason: str
    note: str | None = None


class OutwardApprovalApproveRequest(BaseModel):
    note: str | None = None


def _filter_payload(outbound_filter: Callable[[Any, str], Any] | None, payload: Any, surface: str) -> Any:
    if outbound_filter is None:
        return payload
    return outbound_filter(payload, surface)


def build_approvals_router(
    engine_getter: Callable[[], Any],
    *,
    outward_approval_service_getter: Callable[[], Any] | None = None,
    outward_execution_service_getter: Callable[[], Any] | None = None,
    outbound_filter: Callable[[Any, str], Any] | None = None,
) -> APIRouter:
    router = APIRouter()

    async def _continue_outward_run_after_approval(proposal_id: str) -> None:
        if outward_execution_service_getter is None:
            return
        await outward_execution_service_getter().continue_after_approval(proposal_id)

    @router.get("/approvals")
    async def list_approvals(
        status: str | None = Query(default=None),
        session_id: str | None = Query(default=None),
        request_id: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        if outward_approval_service_getter is not None:
            outward_items = await outward_approval_service_getter().list_pending(
                status=status or "pending",
                run_id=session_id,
                limit=limit,
            )
            if outward_items:
                payload = {
                    "items": [item.to_queue_payload() for item in outward_items],
                    "count": len(outward_items),
                    "filters": {
                        "status": status,
                        "session_id": session_id,
                        "request_id": request_id,
                    },
                }
                return _filter_payload(outbound_filter, payload, "api.approvals.list")
        engine = engine_getter()
        try:
            items = await engine.list_approvals(
                status=status,
                session_id=session_id,
                request_id=request_id,
                limit=limit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        payload = {
            "items": items,
            "count": len(items),
            "filters": {
                "status": status,
                "session_id": session_id,
                "request_id": request_id,
            },
        }
        return _filter_payload(outbound_filter, payload, "api.approvals.list")

    @router.get("/approvals/{approval_id}")
    async def get_approval(approval_id: str) -> Any:
        if outward_approval_service_getter is not None:
            outward = await outward_approval_service_getter().get(approval_id)
            if outward is not None:
                return _filter_payload(outbound_filter, outward.to_decision_payload(), "api.approvals.review")
        engine = engine_getter()
        try:
            approval = await engine.get_approval(approval_id)
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if approval is None:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return _filter_payload(outbound_filter, approval, "api.approvals.review")

    @router.post("/approvals/{approval_id}/approve")
    async def approve_outward_approval(
        approval_id: str,
        req: OutwardApprovalApproveRequest,
        request: Request,
    ) -> Any:
        if outward_approval_service_getter is None:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        try:
            resolved = await outward_approval_service_getter().approve(
                approval_id,
                operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
                note=req.note,
            )
            await _continue_outward_run_after_approval(resolved.proposal_id)
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail.lower() else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        payload = {"status": "resolved", "approval": resolved.to_decision_payload()}
        return _filter_payload(outbound_filter, payload, "api.approvals.approve")

    @router.post("/approvals/{approval_id}/deny")
    async def deny_outward_approval(
        approval_id: str,
        req: OutwardApprovalDenyRequest,
        request: Request,
    ) -> Any:
        if outward_approval_service_getter is None:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        try:
            resolved = await outward_approval_service_getter().deny(
                approval_id,
                operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
                reason=req.reason,
                note=req.note,
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail.lower() else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        payload = {"status": "resolved", "approval": resolved.to_decision_payload()}
        return _filter_payload(outbound_filter, payload, "api.approvals.deny")

    @router.post("/approvals/{approval_id}/decision")
    async def decide_approval(approval_id: str, req: ApprovalDecisionRequest, request: Request) -> Any:
        if outward_approval_service_getter is not None:
            outward = await outward_approval_service_getter().get(approval_id)
            if outward is not None:
                try:
                    if req.decision == "approve":
                        resolved = await outward_approval_service_getter().approve(
                            approval_id,
                            operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
                            note=req.notes,
                        )
                        await _continue_outward_run_after_approval(resolved.proposal_id)
                    elif req.decision == "deny":
                        resolved = await outward_approval_service_getter().deny(
                            approval_id,
                            operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
                            reason=req.notes or "operator_denied",
                        )
                    else:
                        raise HTTPException(status_code=422, detail="decision must be one of: approve, deny")
                except ValueError as exc:
                    detail = str(exc)
                    status_code = 404 if "not found" in detail.lower() else 422
                    raise HTTPException(status_code=status_code, detail=detail) from exc
                except RuntimeError as exc:
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                payload = {"status": "resolved", "approval": resolved.to_decision_payload()}
                return _filter_payload(outbound_filter, payload, "api.approvals.decision")
        engine = engine_getter()
        try:
            result = await engine.decide_approval(
                approval_id=approval_id,
                decision=req.decision,
                edited_proposal=req.edited_proposal,
                notes=req.notes,
                operator_actor_ref=getattr(request.state, "authenticated_actor_ref", None),
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _filter_payload(outbound_filter, result, "api.approvals.decision")

    return router


__all__ = [
    "ApprovalDecisionRequest",
    "OutwardApprovalApproveRequest",
    "OutwardApprovalDenyRequest",
    "build_approvals_router",
]
