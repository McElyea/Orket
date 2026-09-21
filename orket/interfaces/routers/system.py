from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from orket.application.services import api_policy_input_service as api_policy
from orket.interfaces.operator_view_support import build_provider_status_view, build_system_health_view


class SaveFileRequest(BaseModel):
    path: str
    content: str


class RunAssetRequest(BaseModel):
    path: str | None = None
    build_id: str | None = None
    type: str | None = None
    issue_id: str | None = None


class ChatDriverRequest(BaseModel):
    message: str


def build_system_router(
    *,
    project_root_getter: Callable[[], Path],
    runtime_state: Any,
    api_runtime_node_getter: Callable[[], Any],
    system_queries_getter: Callable[[], Any],
    runtime_host_getter: Callable[[], Any],
    now_local: Callable[[], Any],
    events_getter: Callable[[], Any],
    model_selection_getter: Callable[[], Any],
    parse_roles_filter: Callable[[str | None], list[str]],
    discover_active_roles: Callable[[Path], list[str]],
    discover_team_topology: Callable[[Path], list[dict[str, Any]]],
    invoke_async_method: Callable[[object, dict[str, Any], str], Any],
    schedule_async_invocation_task: Callable[[object, dict[str, Any], str, str], Any],
    engine_getter: Callable[[], Any],
) -> APIRouter:
    router = APIRouter()

    def _runtime_state() -> Any:
        return runtime_state() if callable(runtime_state) else runtime_state

    @router.post("/system/clear-logs")
    async def clear_logs() -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        project_root = project_root_getter()
        log_path = api_runtime_node.resolve_clear_logs_path()
        fs = runtime_host.create_file_tools(project_root)
        try:
            invocation = api_runtime_node.resolve_clear_logs_invocation(log_path)
            await invoke_async_method(fs, invocation, "clear logs")
        except (PermissionError, FileNotFoundError, OSError) as exc:
            await events_getter().emit(
                "clear_logs_skipped",
                {"path": log_path, "error": str(exc)},
            )
        return {"ok": True}

    @router.get("/system/heartbeat")
    async def heartbeat() -> dict[str, Any]:
        return {
            "status": "online",
            "timestamp": now_local().isoformat(),
            "active_tasks": await _runtime_state().get_active_task_count(),
        }

    @router.get("/system/metrics")
    async def get_metrics() -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        metrics = await system_queries_getter().hardware_metrics()
        return cast(dict[str, Any], api_policy.normalize_api_metrics(api_runtime_node, metrics))

    @router.get("/system/explorer")
    async def list_system_files(path: str = ".") -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        try:
            return await system_queries_getter().explorer(path, api_runtime_node)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="Forbidden") from exc

    @router.get("/system/read")
    async def read_system_file(path: str) -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        fs = runtime_host.create_file_tools(project_root_getter())
        try:
            invocation = api_runtime_node.resolve_read_invocation(path)
            content = await invoke_async_method(fs, invocation, "read")
        except PermissionError as exc:
            raise HTTPException(
                status_code=403,
                detail=api_runtime_node.permission_denied_detail("read", str(exc)),
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=api_runtime_node.read_not_found_detail(path)) from exc
        return {"content": content}

    @router.post("/system/save")
    async def save_system_file(req: SaveFileRequest) -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        fs = runtime_host.create_file_tools(project_root_getter())
        try:
            invocation = api_runtime_node.resolve_save_invocation(req.path, req.content)
            await invoke_async_method(fs, invocation, "save")
        except PermissionError as exc:
            raise HTTPException(
                status_code=403,
                detail=api_runtime_node.permission_denied_detail("save", str(exc)),
            ) from exc
        return {"ok": True}

    @router.get("/system/calendar")
    async def get_calendar() -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        now = now_local()
        calendar_window = api_runtime_node.calendar_window(now)
        return {
            "current_sprint": system_queries_getter().current_sprint(now),
            "sprint_start": calendar_window["sprint_start"],
            "sprint_end": calendar_window["sprint_end"],
        }

    @router.get("/system/model-assignments")
    async def get_model_assignments(roles: str | None = None) -> dict[str, Any]:
        project_root = project_root_getter()
        engine = engine_getter()
        role_filter = parse_roles_filter(roles)
        active_roles = role_filter or await asyncio.to_thread(discover_active_roles, project_root / "model")
        selector = await model_selection_getter().prepare(engine.org)

        items: list[dict[str, Any]] = []
        for role in active_roles:
            selected = selector.select(role=role)
            decision = selected.to_payload()
            final_model = selected.final_model
            items.append(
                {
                    "role": role,
                    "selected_model": selected.selected_model,
                    "final_model": final_model,
                    "demoted": bool(decision.get("demoted", False)),
                    "reason": str(decision.get("reason") or "unknown"),
                    "dialect": selector.select_dialect(final_model),
                }
            )
            if "score_source" in decision:
                items[-1]["score_source"] = decision["score_source"]
        return {
            "items": items,
            "count": len(items),
            "generated_at": now_local().isoformat(),
            "filters": {"roles": role_filter or None},
        }

    @router.get("/system/provider-status")
    async def get_provider_status(roles: str | None = None) -> dict[str, Any]:
        assignments = await get_model_assignments(roles=roles)
        return build_provider_status_view(list(assignments.get("items") or []))

    @router.get("/system/health-view")
    async def get_system_health_view(roles: str | None = None) -> dict[str, Any]:
        heartbeat_payload = await heartbeat()
        metrics_payload = await get_metrics()
        provider_status = await get_provider_status(roles=roles)
        return build_system_health_view(
            heartbeat=heartbeat_payload,
            metrics=metrics_payload,
            provider_status=provider_status,
        )

    @router.get("/system/teams")
    async def get_system_teams(department: str | None = None) -> dict[str, Any]:
        project_root = project_root_getter()
        topology = await asyncio.to_thread(discover_team_topology, project_root / "model")
        if department:
            dept = str(department).strip().lower()
            topology = [item for item in topology if str(item.get("department") or "").strip().lower() == dept]
        return {
            "items": topology,
            "count": len(topology),
            "filters": {"department": department or None},
        }

    @router.post("/system/run-active")
    async def run_active_asset(req: RunAssetRequest) -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        engine = engine_getter()
        session_id = runtime_host.create_session_id()

        asset_id = api_runtime_node.resolve_asset_id(req.path, req.issue_id)
        if not asset_id:
            raise HTTPException(
                status_code=400,
                detail=api_runtime_node.run_active_missing_asset_detail(),
            )

        invocation = api_runtime_node.resolve_run_active_invocation(
            asset_id=asset_id,
            build_id=req.build_id,
            session_id=session_id,
            request_type=req.type,
        )
        invocation = api_policy.capture_api_invocation(invocation)
        method_name = invocation["method_name"]

        await events_getter().emit(
            "api_run_active",
            {
                "asset_id": asset_id,
                "request_type": req.type,
                "session_id": session_id,
                "method_name": method_name,
            },
        )
        await schedule_async_invocation_task(engine, invocation, "run", session_id)
        return {"session_id": session_id}

    @router.get("/system/board")
    async def get_system_board(dept: str = "core") -> Any:
        return await system_queries_getter().system_board(dept)

    @router.get("/system/preview-asset")
    async def preview_asset(path: str, issue_id: str | None = None) -> Any:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        target = api_policy.capture_preview_target(api_runtime_node.resolve_preview_target(path, issue_id))
        invocation = api_policy.capture_api_invocation(api_runtime_node.resolve_preview_invocation(target, issue_id))
        builder = await runtime_host.create_preview_builder(project_root_getter() / "model")
        return await invoke_async_method(builder, invocation, "preview")

    @router.post("/system/chat-driver")
    async def chat_driver(req: ChatDriverRequest) -> dict[str, Any]:
        api_runtime_node = api_runtime_node_getter()
        runtime_host = runtime_host_getter()
        driver = await runtime_host.create_chat_driver()
        try:
            invocation = api_runtime_node.resolve_chat_driver_invocation(req.message)
            response = await invoke_async_method(driver, invocation, "chat driver")
            return {"response": response}
        finally:
            await runtime_host.close_chat_driver(driver)

    return router
