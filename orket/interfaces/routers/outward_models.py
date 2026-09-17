from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class OutwardModelRecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    execution_generation: int = Field(gt=0, strict=True)
    turn: int = Field(gt=0, strict=True)
    step_index: int = Field(ge=0, strict=True)
    expected_owner_id: str = Field(min_length=1, max_length=128)
    expected_fencing_generation: int = Field(gt=0, strict=True)


def build_outward_models_router(
    *, execution_service_getter: Callable[[], Any], outbound_filter: Callable[[Any, str], Any] | None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/runs/{run_id}/model-admission")
    async def inspect_admission(run_id: str) -> Any:
        try:
            payload = await execution_service_getter().models.recovery.inspect(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outbound_filter(payload, "api.runs.model_admission") if outbound_filter else payload

    @router.post("/runs/{run_id}/model-admission/recover")
    async def recover_admission(run_id: str, body: OutwardModelRecoverRequest, request: Request) -> Any:
        try:
            admission = await execution_service_getter().models.recovery.recover(
                run_id, **body.model_dump(),
                operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
            )
            payload = {"status": "resolved", "admission": admission}
        except ValueError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outbound_filter(payload, "api.runs.model_admission.recover") if outbound_filter else payload

    return router
