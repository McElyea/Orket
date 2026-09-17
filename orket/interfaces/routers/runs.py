from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from orket.application.services.operator_completion_service import load_operator_run_projection
from orket.interfaces.operator_view_models import build_run_detail_view, build_run_history_item_view
from orket.interfaces.routers.outward_models import build_outward_models_router


def build_runs_router(
    engine_getter: Callable[[], Any], *, outward_execution_service_getter: Callable[[], Any] | None = None,
    outbound_filter: Callable[[Any, str], Any] | None = None,
) -> APIRouter:
    router = APIRouter()

    async def _load_run_projection(session_id: str) -> dict[str, Any]:
        projection = await load_operator_run_projection(engine=engine_getter(), session_id=session_id)
        if projection is None:
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
        return projection

    @router.get("/runs/view")
    async def list_run_views(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        engine = engine_getter()
        recent_runs = await engine.sessions.get_recent_runs(limit=limit)
        items: list[dict[str, Any]] = []
        for row in recent_runs:
            session_id = str((row or {}).get("id") or (row or {}).get("session_id") or "").strip()
            if not session_id:
                continue
            projection = await _load_run_projection(session_id)
            items.append(build_run_history_item_view(**projection))
        return {
            "items": items,
            "count": len(items),
            "limit": limit,
        }

    @router.get("/runs/{session_id}/view")
    async def get_run_view(session_id: str) -> dict[str, Any]:
        projection = await _load_run_projection(session_id)
        return build_run_detail_view(**projection)

    if outward_execution_service_getter is not None:
        router.include_router(build_outward_models_router(
            execution_service_getter=outward_execution_service_getter, outbound_filter=outbound_filter,
        ))
    return router
