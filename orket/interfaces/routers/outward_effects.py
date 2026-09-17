from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class OutwardEffectRecoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    expected_owner_id: str = Field(min_length=1, max_length=128)
    expected_fencing_generation: int = Field(gt=0, strict=True)


def build_outward_effects_router(
    *, execution_service_getter: Callable[[], Any], outbound_filter: Callable[[Any, str], Any] | None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/approvals/{approval_id}/effect")
    async def inspect_effect(approval_id: str) -> Any:
        try:
            payload = await execution_service_getter().effects.inspect(approval_id)
        except ValueError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outbound_filter(payload, "api.approvals.effect") if outbound_filter else payload

    @router.post("/approvals/{approval_id}/effect/recover")
    async def recover_effect(approval_id: str, body: OutwardEffectRecoverRequest, request: Request) -> Any:
        try:
            service = execution_service_getter()
            await service.recover_effect(
                approval_id, **body.model_dump(),
                operator_ref=getattr(request.state, "authenticated_actor_ref", None) or "operator:unknown",
            )
            payload = {"status": "resolved", "effect": await service.effects.inspect(approval_id)}
        except ValueError as exc:
            raise HTTPException(status_code=404 if "not found" in str(exc) else 422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outbound_filter(payload, "api.approvals.effect.recover") if outbound_filter else payload

    return router
