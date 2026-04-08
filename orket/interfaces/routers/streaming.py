from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def register_streaming_routes(
    app: FastAPI,
    *,
    api_key_name: str,
    api_runtime_node_getter: Callable[[], Any],
    runtime_host_getter: Callable[[], Any],
    interaction_manager_getter: Callable[[], Any],
    stream_bus_getter: Callable[[], Any],
    runtime_state: Any,
    project_root_getter: Callable[[], Path],
    log_event: Callable[[str, dict[str, Any], Path], None],
) -> None:
    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket) -> None:
        api_runtime_node = api_runtime_node_getter()
        expected_key = os.getenv("ORKET_API_KEY")
        header_key = websocket.headers.get(api_key_name) or websocket.headers.get(api_key_name.lower())
        query_key = websocket.query_params.get("api_key")
        supplied_key = api_runtime_node.resolve_websocket_api_key(header_key, query_key)
        warning_event = api_runtime_node.websocket_query_compat_warning_event(
            bool((not header_key) and query_key and supplied_key == query_key),
            input_ref="/ws/events",
            timestamp_utc=runtime_host_getter().utc_now_iso(),
        )
        if warning_event:
            log_event("security_compat_fallback_used", warning_event, project_root_getter())
        if not api_runtime_node.is_api_key_valid(expected_key, supplied_key):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        await runtime_state.add_websocket(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await runtime_state.remove_websocket(websocket)

    @app.websocket("/ws/interactions/{session_id}")
    async def websocket_interactions(session_id: str, websocket: WebSocket) -> None:
        api_runtime_node = api_runtime_node_getter()
        interaction_manager = interaction_manager_getter()
        expected_key = os.getenv("ORKET_API_KEY")
        header_key = websocket.headers.get(api_key_name) or websocket.headers.get(api_key_name.lower())
        query_key = websocket.query_params.get("api_key")
        supplied_key = api_runtime_node.resolve_websocket_api_key(header_key, query_key)
        warning_event = api_runtime_node.websocket_query_compat_warning_event(
            bool((not header_key) and query_key and supplied_key == query_key),
            input_ref=f"/ws/interactions/{session_id}",
            timestamp_utc=runtime_host_getter().utc_now_iso(),
        )
        if warning_event:
            log_event("security_compat_fallback_used", warning_event, project_root_getter())
        if not api_runtime_node.is_api_key_valid(expected_key, supplied_key):
            await websocket.close(code=4403)
            return
        if not interaction_manager.stream_enabled():
            await websocket.close(code=4400)
            return
        await websocket.accept()
        queue = await interaction_manager.subscribe(session_id)
        try:
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump())
        except WebSocketDisconnect:
            pass
        finally:
            await stream_bus_getter().unsubscribe(session_id, queue)
