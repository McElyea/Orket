from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
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
    sanitization_digest: Optional[str] = None
    revalidate_policy_forbidden: bool = False


class KernelEndSessionRequest(BaseModel):
    session_id: str
    trace_id: str
    request_id: Optional[str] = None
    reason: Optional[str] = None


def build_kernel_router(engine_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

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
            return engine.kernel_admit_proposal(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": req.session_id,
                    "trace_id": req.trace_id,
                    "request_id": req.request_id,
                    "proposal": req.proposal,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/kernel/commit-proposal")
    async def kernel_commit_proposal(req: KernelCommitProposalRequest):
        engine = engine_getter()
        try:
            return engine.kernel_commit_proposal(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": req.session_id,
                    "trace_id": req.trace_id,
                    "request_id": req.request_id,
                    "proposal_digest": req.proposal_digest,
                    "admission_decision_digest": req.admission_decision_digest,
                    "approval_id": req.approval_id,
                    "execution_result_digest": req.execution_result_digest,
                    "sanitization_digest": req.sanitization_digest,
                    "revalidate_policy_forbidden": req.revalidate_policy_forbidden,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/kernel/end-session")
    async def kernel_end_session(req: KernelEndSessionRequest):
        engine = engine_getter()
        try:
            return engine.kernel_end_session(
                {
                    "contract_version": "kernel_api/v1",
                    "session_id": req.session_id,
                    "trace_id": req.trace_id,
                    "request_id": req.request_id,
                    "reason": req.reason,
                }
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    router.include_router(build_approvals_router(engine_getter))

    return router
