from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from orket.adapters.storage.async_flow_repository import AsyncFlowRepository
from orket.application.services.flow_authoring_service import (
    FlowAuthoringConflictError,
    FlowAuthoringNotFoundError,
    FlowAuthoringService,
    FlowDefinitionWriteModel,
    FlowRuntimeNotAdmittedError,
)
from orket.exceptions import CardNotFound
from orket.runtime_paths import resolve_flow_authoring_db_path


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
    project_root_getter: Callable[[], Path],
    schedule_async_invocation_task: Callable[[object, dict[str, Any], str, str], Awaitable[None]],
    session_id_factory: Callable[[], str],
) -> APIRouter:
    router = APIRouter()

    def _service() -> FlowAuthoringService:
        return FlowAuthoringService(
            flow_repo=AsyncFlowRepository(
                resolve_flow_authoring_db_path(project_root_getter() / ".orket" / "durable" / "db" / "orket_ui_flows.sqlite3")
            ),
            now_iso_factory=lambda: datetime.now(UTC).isoformat(),
            flow_id_factory=lambda: f"FLOW-{uuid4().hex[:8].upper()}",
            revision_id_factory=lambda: f"frv_{uuid4().hex}",
        )

    @router.get("/flows")
    async def list_flows(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)) -> dict[str, Any]:
        return await _service().list_flows(limit=limit, offset=offset)

    @router.get("/flows/{flow_id}")
    async def get_flow(flow_id: str) -> dict[str, Any]:
        try:
            return await _service().get_flow(flow_id)
        except FlowAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Flow '{exc}' not found") from exc

    @router.post("/flows")
    async def create_flow(req: FlowCreateRequest) -> dict[str, Any]:
        result = await _service().create_flow(req.definition)
        return result.model_dump()

    @router.put("/flows/{flow_id}")
    async def save_flow(flow_id: str, req: FlowUpdateRequest) -> dict[str, Any]:
        try:
            result = await _service().update_flow(
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
        result = _service().validate_definition(req.definition)
        return result.model_dump()

    @router.post("/flows/{flow_id}/runs")
    async def run_flow(flow_id: str, req: FlowRunRequest) -> dict[str, Any]:
        service = _service()
        try:
            revision_id, assigned_card_id = await service.prepare_flow_run(
                flow_id=flow_id,
                expected_revision_id=req.expected_revision_id,
            )
        except FlowAuthoringNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"Flow '{exc}' not found") from exc
        except FlowAuthoringConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except FlowRuntimeNotAdmittedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        engine = engine_getter()
        existing_card = await engine.cards.get_by_id(assigned_card_id)
        if existing_card is None:
            raise HTTPException(
                status_code=409,
                detail="current_flow_run_slice_requires_assigned_card_present_on_host_card_surface",
            )
        try:
            target_kind, _parent_epic_name = await engine.resolve_run_card_target(assigned_card_id)
        except CardNotFound as exc:
            raise HTTPException(
                status_code=409,
                detail="current_flow_run_slice_requires_assigned_card_resolve_on_canonical_run_card_surface",
            ) from exc
        if target_kind != "issue":
            raise HTTPException(
                status_code=409,
                detail="current_flow_run_slice_requires_assigned_card_resolve_to_issue_runtime_target",
            )

        session_id = session_id_factory()
        await schedule_async_invocation_task(
            engine,
            {
                "method_name": "run_issue",
                "args": [assigned_card_id],
                "kwargs": {"session_id": session_id},
            },
            "run",
            session_id,
        )
        return {
            "flow_id": flow_id,
            "revision_id": revision_id,
            "session_id": session_id,
            "accepted_at": datetime.now(UTC).isoformat(),
            "summary": "Accepted through the bounded single-card flow run surface.",
        }

    return router
