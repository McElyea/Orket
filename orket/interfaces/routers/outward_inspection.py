"""Outward run inspection transport using the existing application owners."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from orket.application.services.outward_run_inspection_service import OutwardRunInspectionError


def _parse_event_types(types: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(types or "").split(",") if item.strip())


async def _stream_outward_run_events(
    run_id, types, *, run_service_getter, inspection_service_getter, outbound_filter,
) -> AsyncIterator[str]:
    seen: set[str] = set()
    event_types = _parse_event_types(types)
    while True:
        payload = await inspection_service_getter().events(run_id, types=event_types)
        emitted = False
        for event in payload["events"]:
            event_id = str(event.get("event_id") or "")
            if event_id in seen:
                continue
            seen.add(event_id)
            filtered = outbound_filter(event, surface="api.runs.events.stream")
            yield f"event: run_event\ndata: {json.dumps(filtered, sort_keys=True)}\n\n"
            emitted = True
        run = await run_service_getter().get_status(run_id)
        if run is None or run.status in {"completed", "failed"}:
            break
        if not emitted:
            yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(1.0)


def build_outward_inspection_router(
    *, run_service_getter: Callable[[], Any], inspection_service_getter: Callable[[], Any],
    outbound_filter: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()

    @router.get("/runs/{run_id}/events")
    async def get_outward_run_events(
        run_id: str,
        from_turn: int | None = Query(default=None, ge=0),
        to_turn: int | None = Query(default=None, ge=0),
        types: str | None = Query(default=None),
        agent_id: str | None = Query(default=None),
        limit: int = Query(default=1000, ge=1, le=5000),
    ) -> dict[str, Any]:
        try:
            payload = await inspection_service_getter().events(
                run_id,
                from_turn=from_turn,
                to_turn=to_turn,
                types=_parse_event_types(types),
                agent_id=agent_id,
                limit=limit,
            )
        except OutwardRunInspectionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return cast(dict[str, Any], outbound_filter(payload, surface="api.runs.events"))

    @router.get("/runs/{run_id}/summary")
    async def get_outward_run_summary(run_id: str) -> dict[str, Any]:
        try:
            payload = await inspection_service_getter().summary(run_id)
        except OutwardRunInspectionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return cast(dict[str, Any], outbound_filter(payload, surface="api.runs.summary"))

    @router.get("/runs/{run_id}/events/stream")
    async def stream_outward_run_events(
        run_id: str,
        types: str | None = Query(default=None),
    ) -> StreamingResponse:
        if await run_service_getter().get_status(run_id) is None:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        stream = _stream_outward_run_events(run_id, types, run_service_getter=run_service_getter,
            inspection_service_getter=inspection_service_getter, outbound_filter=outbound_filter)
        return StreamingResponse(stream, media_type="text/event-stream")

    return router
