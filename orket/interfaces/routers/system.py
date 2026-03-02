from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class SaveFileRequest(BaseModel):
    path: str
    content: str


class RunAssetRequest(BaseModel):
    path: Optional[str] = None
    build_id: Optional[str] = None
    type: Optional[str] = None
    issue_id: Optional[str] = None


class ChatDriverRequest(BaseModel):
    message: str


def build_system_router(
    *,
    project_root_getter: Callable[[], Path],
    runtime_state: Any,
    api_runtime_node_getter: Callable[[], Any],
    now_local: Callable[[], Any],
    get_metrics_snapshot: Callable[[], dict[str, Any]],
    log_event: Callable[[str, dict[str, Any], Path], None],
    model_selector_factory: Callable[[Any, dict[str, Any], dict[str, Any]], Any],
    load_user_preferences: Callable[[], dict[str, Any]],
    load_user_settings: Callable[[], dict[str, Any]],
    parse_roles_filter: Callable[[Optional[str]], list[str]],
    discover_active_roles: Callable[[Path], list[str]],
    discover_team_topology: Callable[[Path], list[dict[str, Any]]],
    invoke_async_method: Callable[[object, dict, str], Any],
    schedule_async_invocation_task: Callable[[object, dict, str, str], Any],
    engine_getter: Callable[[], Any],
) -> APIRouter:
    router = APIRouter()

    @router.post("/system/clear-logs")
    async def clear_logs():
        api_runtime_node = api_runtime_node_getter()
        project_root = project_root_getter()
        log_path = api_runtime_node.resolve_clear_logs_path()
        fs = api_runtime_node.create_file_tools(project_root)
        try:
            invocation = api_runtime_node.resolve_clear_logs_invocation(log_path)
            await invoke_async_method(fs, invocation, "clear logs")
        except (PermissionError, FileNotFoundError, OSError) as exc:
            log_event(
                "clear_logs_skipped",
                {"path": log_path, "error": str(exc)},
                project_root,
            )
        return {"ok": True}

    @router.get("/system/heartbeat")
    async def heartbeat():
        return {
            "status": "online",
            "timestamp": now_local().isoformat(),
            "active_tasks": len(runtime_state.active_tasks),
        }

    @router.get("/system/metrics")
    async def get_metrics():
        api_runtime_node = api_runtime_node_getter()
        metrics = await asyncio.to_thread(get_metrics_snapshot)
        return api_runtime_node.normalize_metrics(metrics)

    @router.get("/system/explorer")
    async def list_system_files(path: str = "."):
        api_runtime_node = api_runtime_node_getter()
        project_root = project_root_getter()
        target = api_runtime_node.resolve_explorer_path(project_root, path)
        if target is None:
            raise HTTPException(**api_runtime_node.resolve_explorer_forbidden_error(path))
        if not target.exists():
            return api_runtime_node.resolve_explorer_missing_response(path)

        items = []
        for entry in target.iterdir():
            if not api_runtime_node.include_explorer_entry(entry.name):
                continue
            is_dir = entry.is_dir()
            items.append({"name": entry.name, "is_dir": is_dir, "ext": entry.suffix})
        return {"items": api_runtime_node.sort_explorer_items(items), "path": path}

    @router.get("/system/read")
    async def read_system_file(path: str):
        api_runtime_node = api_runtime_node_getter()
        fs = api_runtime_node.create_file_tools(project_root_getter())
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
    async def save_system_file(req: SaveFileRequest):
        api_runtime_node = api_runtime_node_getter()
        fs = api_runtime_node.create_file_tools(project_root_getter())
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
    async def get_calendar():
        api_runtime_node = api_runtime_node_getter()
        now = now_local()
        calendar_window = api_runtime_node.calendar_window(now)
        return {
            "current_sprint": api_runtime_node.resolve_current_sprint(now),
            "sprint_start": calendar_window["sprint_start"],
            "sprint_end": calendar_window["sprint_end"],
        }

    @router.get("/system/model-assignments")
    async def get_model_assignments(roles: Optional[str] = None):
        project_root = project_root_getter()
        engine = engine_getter()
        role_filter = parse_roles_filter(roles)
        active_roles = role_filter or await asyncio.to_thread(discover_active_roles, project_root / "model")
        selector = model_selector_factory(engine.org, load_user_preferences(), load_user_settings())

        items: list[dict[str, Any]] = []
        for role in active_roles:
            selected_model = selector.select(role=role)
            decision = selector.get_last_selection_decision()
            final_model = str(decision.get("final_model") or selected_model)
            items.append(
                {
                    "role": role,
                    "selected_model": str(decision.get("selected_model") or selected_model),
                    "final_model": final_model,
                    "demoted": bool(decision.get("demoted", False)),
                    "reason": str(decision.get("reason") or "unknown"),
                    "dialect": selector.get_dialect_name(final_model),
                }
            )
        return {
            "items": items,
            "count": len(items),
            "generated_at": now_local().isoformat(),
            "filters": {"roles": role_filter or None},
        }

    @router.get("/system/teams")
    async def get_system_teams(department: Optional[str] = None):
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
    async def run_active_asset(req: RunAssetRequest):
        api_runtime_node = api_runtime_node_getter()
        engine = engine_getter()
        project_root = project_root_getter()
        session_id = api_runtime_node.create_session_id()

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
        method_name = invocation["method_name"]

        log_event(
            "api_run_active",
            {
                "asset_id": asset_id,
                "request_type": req.type,
                "session_id": session_id,
                "method_name": method_name,
            },
            project_root,
        )
        await schedule_async_invocation_task(engine, invocation, "run", session_id)
        return {"session_id": session_id}

    @router.get("/system/board")
    async def get_system_board(dept: str = "core"):
        api_runtime_node = api_runtime_node_getter()
        return api_runtime_node.resolve_system_board(dept)

    @router.get("/system/preview-asset")
    async def preview_asset(path: str, issue_id: Optional[str] = None):
        api_runtime_node = api_runtime_node_getter()
        target = api_runtime_node.resolve_preview_target(path, issue_id)
        invocation = api_runtime_node.resolve_preview_invocation(target, issue_id)
        builder = api_runtime_node.create_preview_builder(project_root_getter() / "model")
        return await invoke_async_method(builder, invocation, "preview")

    @router.post("/system/chat-driver")
    async def chat_driver(req: ChatDriverRequest):
        api_runtime_node = api_runtime_node_getter()
        driver = api_runtime_node.create_chat_driver()
        invocation = api_runtime_node.resolve_chat_driver_invocation(req.message)
        response = await invoke_async_method(driver, invocation, "chat driver")
        return {"response": response}

    return router
