from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


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
    turn_id: Optional[str] = None


def build_sessions_router(
    *,
    interaction_manager_getter: Callable[[], Any],
    extension_manager_getter: Callable[[], Any],
    is_builtin_workload: Callable[[str], bool],
    validate_builtin_workload_start: Callable[..., None],
    run_builtin_workload: Callable[..., Any],
    commit_intent_factory: Callable[[str], Any],
) -> APIRouter:
    router = APIRouter()

    @router.post("/interactions/sessions")
    async def start_interaction_session(req: InteractionSessionStartRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        session_id = await interaction_manager.start(req.session_params)
        return {"session_id": session_id}

    @router.post("/interactions/{session_id}/turns")
    async def begin_interaction_turn(session_id: str, req: InteractionTurnRequest):
        interaction_manager = interaction_manager_getter()
        extension_manager = extension_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        workload_id = str(req.workload_id or "").strip()
        if not workload_id:
            raise HTTPException(status_code=400, detail="workload_id is required")
        extension_match = extension_manager.resolve_workload(workload_id)
        if not is_builtin_workload(workload_id) and extension_match is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown workload '{workload_id}'. Built-in workloads: "
                    "stream_test_v1, model_stream_v1, rulesim_v0, marshaller_v0."
                ),
            )
        if is_builtin_workload(workload_id):
            try:
                validate_builtin_workload_start(
                    workload_id=workload_id,
                    input_config=req.input_config,
                    turn_params=req.turn_params,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            turn_id = await interaction_manager.begin_turn(
                session_id=session_id,
                input_payload=req.input_config,
                turn_params=req.turn_params,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        context = await interaction_manager.create_context(session_id, turn_id)
        workspace = Path(req.workspace).resolve()

        async def _run_turn():
            try:
                if is_builtin_workload(workload_id):
                    hints = await run_builtin_workload(
                        workload_id=workload_id,
                        input_config=req.input_config,
                        turn_params=req.turn_params,
                        interaction_context=context,
                    )
                    if int(hints.get("request_cancel_turn", 0) or 0) > 0:
                        await interaction_manager.cancel(turn_id)
                    await interaction_manager.finalize(session_id, turn_id)
                    post_finalize_wait_ms = int(hints.get("post_finalize_wait_ms", 0))
                    if post_finalize_wait_ms > 0:
                        await asyncio.sleep(post_finalize_wait_ms / 1000.0)
                else:
                    await extension_manager.run_workload(
                        workload_id=workload_id,
                        input_config=req.input_config,
                        workspace=workspace,
                        department=req.department,
                        interaction_context=context,
                    )
                    await interaction_manager.finalize(session_id, turn_id)
            except (RuntimeError, ValueError, TypeError, OSError, asyncio.TimeoutError) as exc:
                await interaction_manager.cancel(turn_id)
                await context.request_commit(commit_intent_factory(str(exc)))
                await interaction_manager.finalize(session_id, turn_id)

        _logger = logging.getLogger(__name__)
        def _log_turn_failure(done_task: asyncio.Task[Any]) -> None:
            try:
                error = done_task.exception()
            except asyncio.CancelledError:
                return
            if error is not None:
                _logger.error(
                    "interaction turn failed: session=%s turn=%s error=%s",
                    session_id,
                    turn_id,
                    error,
                )

        task = asyncio.create_task(_run_turn())
        task.add_done_callback(_log_turn_failure)
        return {"session_id": session_id, "turn_id": turn_id}

    @router.post("/interactions/{session_id}/finalize")
    async def finalize_interaction_turn(session_id: str, req: InteractionFinalizeRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        try:
            handle = await interaction_manager.finalize(session_id, req.turn_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return handle.model_dump()

    @router.post("/interactions/{session_id}/cancel")
    async def cancel_interaction(session_id: str, req: InteractionCancelRequest):
        interaction_manager = interaction_manager_getter()
        if not interaction_manager.stream_enabled():
            raise HTTPException(status_code=400, detail="Stream events v1 is disabled.")
        target = req.turn_id or session_id
        try:
            await interaction_manager.cancel(target)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "target": target}

    return router
