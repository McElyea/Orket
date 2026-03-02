from __future__ import annotations

from typing import Any, Callable, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel


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

    return router
