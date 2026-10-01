"""API transport over the existing application query and lifetime owners."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from orket.application.services.outward_run_execution_service import OutwardRunExecutionValidationError
from orket.application.services.outward_run_service import OutwardRunConflictError, OutwardRunValidationError
from orket.interfaces.api_invocation import invoke_api_method

_RUN_SUBMISSION_BODY = Body(...)


def build_outward_runs_router(
    *, runtime_getter, outbound_filter,
) -> APIRouter:
    router = APIRouter()

    @router.post("/runs")
    async def submit_run(payload: dict[str, Any] = _RUN_SUBMISSION_BODY) -> dict[str, Any]:
        try:
            record = await runtime_getter().outward_run_service.submit(payload)
            record = await runtime_getter().outward_run_execution_service.start_if_ready(record.run_id)
        except OutwardRunValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OutwardRunExecutionValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OutwardRunConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return outbound_filter(await runtime_getter().outward_run_service.status_payload(record.run_id), surface="api.runs.submit")

    @router.get("/runs")
    async def list_runs(
        status: str | None = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> Any:
        records = await runtime_getter().outward_run_service.list_runs(status=status, limit=limit, offset=offset)
        if records or status is not None or limit != 20 or offset != 0:
            payload = {
                "items": [await runtime_getter().outward_run_service.status_payload(record.run_id) for record in records],
                "count": len(records),
                "limit": limit,
                "offset": offset,
                "filters": {"status": status},
            }
            return outbound_filter(payload, surface="api.runs.list")
        invocation = runtime_getter().api_runtime_node.resolve_runs_invocation()
        runtime_engine = runtime_getter().engine
        payload = await invoke_api_method(runtime_engine.sessions, invocation, "runs")
        return outbound_filter(payload, surface="api.runs.list")

    return router
