"""API transport over the existing application query and lifetime owners."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query


def _coerce_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: '{value}'") from exc


class LogEndpoints:
    def __init__(self, runtime_getter):
        self._runtime = runtime_getter

    async def list_logs(
        self,
        session_id: str | None = None,
        event: str | None = None,
        role: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = Query(default=200, ge=1, le=2000),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        start_dt = _coerce_datetime(start_time)
        end_dt = _coerce_datetime(end_time)
        try:
            page = await self._runtime().run_queries.logs(
                session_id=session_id, event=event, role=role, start_dt=start_dt, end_dt=end_dt,
                limit=limit, offset=offset,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {**page, "filters": {"session_id": session_id, "event": event, "role": role,
                                   "start_time": start_time, "end_time": end_time}}

def build_logs_router(*, runtime_getter) -> APIRouter:
    router = APIRouter()
    endpoints = LogEndpoints(runtime_getter)
    router.add_api_route("/logs", endpoints.list_logs, methods=["GET"])
    return router
