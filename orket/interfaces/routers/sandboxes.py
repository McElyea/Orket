"""API transport over the existing application query and lifetime owners."""
from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from orket.application.services import api_policy_input_service as api_policy
from orket.application.services.runtime_inspection_service import read_runtime_sandbox_logs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.interfaces.api_invocation import invoke_api_method, resolve_api_method


def build_sandboxes_router(
    *, runtime_getter,
) -> APIRouter:
    router = APIRouter()

    @router.get("/sandboxes")
    async def list_sandboxes() -> Any:
        invocation = runtime_getter().api_runtime_node.resolve_sandboxes_list_invocation()
        runtime_engine = runtime_getter().engine
        return await invoke_api_method(runtime_engine, invocation, "sandboxes")

    @router.post("/sandboxes/{sandbox_id}/stop")
    async def stop_sandbox(sandbox_id: str, request: Request) -> dict[str, bool]:
        invocation = runtime_getter().api_runtime_node.resolve_sandbox_stop_invocation(sandbox_id)
        operator_actor_ref = getattr(request.state, "authenticated_actor_ref", None)
        if operator_actor_ref is not None:
            invocation = {
                **invocation,
                "kwargs": {
                    **dict(invocation.get("kwargs", {})),
                    "operator_actor_ref": operator_actor_ref,
                },
            }
        try:
            runtime_engine = runtime_getter().engine
            await invoke_api_method(runtime_engine, invocation, "sandbox stop")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True}

    @router.get("/sandboxes/{sandbox_id}/logs")
    async def get_sandbox_logs(sandbox_id: str, service: str | None = None) -> dict[str, Any]:
        runtime_node = runtime_getter().api_runtime_node
        construct = partial(runtime_getter().api_runtime_host.create_execution_pipeline,
                            runtime_node.resolve_sandbox_workspace(Path(runtime_getter().project_root)))
        invocation = api_policy.capture_api_invocation(runtime_node.resolve_sandbox_logs_invocation(sandbox_id, service))
        async with open_runtime_owner(construct, label="api-sandbox-log-construction") as pipeline:
            method = resolve_api_method(pipeline.sandbox_orchestrator, invocation, "sandbox logs")
            read = partial(method, *invocation.get("args", []), **invocation.get("kwargs", {}))
            return {"logs": await read_runtime_sandbox_logs(read)}

    return router
