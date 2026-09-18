from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.flow_authoring_service import (
    FlowAuthoringConflictError,
    FlowAuthoringNotFoundError,
    FlowDefinitionWriteModel,
    FlowRuntimeNotAdmittedError,
)
from orket.application.services.flow_runtime_service import accept_flow_run


class FlowCreateRequest(BaseModel):
    definition: FlowDefinitionWriteModel


class FlowUpdateRequest(BaseModel):
    definition: FlowDefinitionWriteModel
    expected_revision_id: str | None = None


class FlowValidationRequest(BaseModel):
    definition: FlowDefinitionWriteModel


class FlowRunRequest(BaseModel):
    expected_revision_id: str | None = None


def build_flows_router(
    *,
    engine_getter: Callable[[], Any],
    host_getter: Callable[[], ApiRuntimeHostService],
    schedule_async_invocation_task: Callable[[object, dict[str, Any], str, str], Awaitable[None]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/flows")
    async def list_flows(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
        return await host_getter().create_flow_authoring_service().list_flows(limit=limit, offset=offset)

    @router.get("/flows/{flow_id}")
    async def get_flow(flow_id: str) -> dict[str, Any]:
        try:
            return await host_getter().create_flow_authoring_service().get_flow(flow_id)
        except FlowAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Flow '{exc}' not found") from exc

    @router.post("/flows")
    async def create_flow(req: FlowCreateRequest) -> dict[str, Any]:
        try:
            result = await host_getter().create_flow_authoring_service().create_flow(req.definition)
        except FlowAuthoringConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result.model_dump()

    @router.put("/flows/{flow_id}")
    async def save_flow(flow_id: str, req: FlowUpdateRequest) -> dict[str, Any]:
        try:
            result = await host_getter().create_flow_authoring_service().update_flow(
                flow_id=flow_id,
                definition=req.definition,
                expected_revision_id=req.expected_revision_id,
            )
        except FlowAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Flow '{exc}' not found") from exc
        except FlowAuthoringConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result.model_dump()

    @router.post("/flows/validate")
    async def validate_flow(req: FlowValidationRequest) -> dict[str, Any]:
        result = host_getter().create_flow_authoring_service().validate_definition(req.definition)
        return result.model_dump()

    @router.post("/flows/{flow_id}/runs")
    async def run_flow(flow_id: str, req: FlowRunRequest) -> dict[str, Any]:
        host = host_getter()
        try:
            result = await accept_flow_run(
                service=host.create_flow_authoring_service(), engine=engine_getter(),
                flow_id=flow_id,
                expected_revision_id=req.expected_revision_id,
                runtime_inputs=host.runtime_inputs, schedule=schedule_async_invocation_task,
            )
        except FlowAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Flow '{exc}' not found") from exc
        except FlowAuthoringConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FlowRuntimeNotAdmittedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        return result.model_dump()

    return router
