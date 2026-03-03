from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


class ApprovalDecisionRequest(BaseModel):
    decision: str
    edited_proposal: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


def build_approvals_router(engine_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/approvals")
    async def list_approvals(
        status: Optional[str] = Query(default=None),
        session_id: Optional[str] = Query(default=None),
        request_id: Optional[str] = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
    ):
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
        return {
            "items": items,
            "count": len(items),
            "filters": {
                "status": status,
                "session_id": session_id,
                "request_id": request_id,
            },
        }

    @router.get("/approvals/{approval_id}")
    async def get_approval(approval_id: str):
        engine = engine_getter()
        approval = await engine.get_approval(approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found")
        return approval

    @router.post("/approvals/{approval_id}/decision")
    async def decide_approval(approval_id: str, req: ApprovalDecisionRequest):
        engine = engine_getter()
        try:
            result = await engine.decide_approval(
                approval_id=approval_id,
                decision=req.decision,
                edited_proposal=req.edited_proposal,
                notes=req.notes,
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail else 422
            raise HTTPException(status_code=status_code, detail=detail) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result

    return router


__all__ = ["ApprovalDecisionRequest", "build_approvals_router"]
