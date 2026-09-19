from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from orket.application.interactions.commands import InteractionCommands, InteractionUnavailable
from orket.application.services.interaction_cancellation_service import (
    InteractionCancelConflict,
    InteractionCancelDisabled,
    InteractionCancellationService,
    InteractionCancelNotFound,
)
from orket.application.services.protocol_replay_service import ProtocolReplayService
from orket.interfaces.routers.protocol_queries import build_protocol_query_router


class InteractionSessionStartRequest(BaseModel):
    session_params: dict[str, Any] = Field(default_factory=dict)


class InteractionTurnRequest(BaseModel):
    workload_id: str
    input_config: dict[str, Any] = Field(default_factory=dict)
    department: str = "core"
    workspace: str = "workspace/default"
    turn_params: dict[str, Any] = Field(default_factory=dict)


class InteractionFinalizeRequest(BaseModel):
    turn_id: str


class InteractionCancelRequest(BaseModel):
    turn_id: str | None = None


def build_sessions_router(
    *,
    turn_service_getter: Callable[[], InteractionCommands],
    workspace_root_getter: Callable[[], Path] = Path.cwd,
    protocol_replay_service_getter: Callable[[], Any] | None = None,
    cancellation_service_getter: Callable[[], InteractionCancellationService] | None = None,
) -> APIRouter:
    router = APIRouter()

    def _workspace_root() -> Path:
        return workspace_root_getter().resolve()

    def _get_protocol_replay_service() -> Any:
        if protocol_replay_service_getter is not None:
            return protocol_replay_service_getter()
        return ProtocolReplayService(workspace_root=workspace_root_getter())

    @router.post("/interactions/sessions")
    async def start_interaction_session(req: InteractionSessionStartRequest) -> dict[str, Any]:
        try:
            return await turn_service_getter().start(req.session_params)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/interactions/{session_id}/turns")
    async def begin_interaction_turn(session_id: str, req: InteractionTurnRequest) -> dict[str, Any]:
        try:
            return await turn_service_getter().begin(session_id, **req.model_dump())
        except InteractionUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/interactions/{session_id}/finalize")
    async def finalize_interaction_turn(session_id: str, req: InteractionFinalizeRequest) -> dict[str, Any]:
        try:
            return await turn_service_getter().finalize(session_id, req.turn_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/interactions/{session_id}/cancel")
    async def cancel_interaction(
        session_id: str,
        req: InteractionCancelRequest,
        request: Request,
    ) -> dict[str, Any]:
        if cancellation_service_getter is None:
            raise HTTPException(status_code=503, detail="Interaction cancellation service is unavailable.")
        service = cancellation_service_getter()
        actor_ref = str(getattr(request.state, "authenticated_actor_ref", "") or "").strip()
        try:
            return await service.cancel(session_id=session_id, turn_id=req.turn_id, actor_ref=actor_ref)
        except InteractionCancelNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InteractionCancelConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InteractionCancelDisabled as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/marshaller/runs")
    async def list_marshaller_run_rows(limit: int = 20) -> dict[str, Any]:
        from orket.marshaller.cli import list_marshaller_runs

        workspace_root = _workspace_root()
        rows = await list_marshaller_runs(workspace_root, limit=max(1, int(limit)))
        return {"runs": rows}

    @router.get("/marshaller/runs/{run_id}")
    async def inspect_marshaller_run(run_id: str, attempt_index: int | None = None) -> Any:
        from orket.marshaller.cli import inspect_marshaller_attempt

        workspace_root = _workspace_root()
        try:
            return await inspect_marshaller_attempt(
                workspace_root,
                run_id=run_id,
                attempt_index=attempt_index,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    router.include_router(build_protocol_query_router(_get_protocol_replay_service))
    return router
