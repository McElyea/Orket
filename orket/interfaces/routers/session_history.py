"""API transport over the existing application query and lifetime owners."""
from __future__ import annotations

import asyncio
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.application.services.runtime_inspection_service import read_runtime_replay
from orket.interfaces.api_invocation import invoke_api_method
from orket.interfaces.routers.run_history import read_run_replay_turns


def _runtime_task_summary(tasks: list[asyncio.Task[Any]]) -> tuple[bool, str]:
    active_tasks = [task for task in tasks if not task.done()]
    if active_tasks:
        return True, "running"
    if any(task.done() and not task.cancelled() for task in tasks):
        return False, "completed"
    if any(task.cancelled() for task in tasks):
        return False, "canceled"
    return False, "idle"


class SessionHistoryEndpoints:
    def __init__(self, runtime_getter):
        self._runtime = runtime_getter

    async def get_session_detail(self, session_id: str) -> Any:
        await self._runtime().events.emit("api_session_detail", {"session_id": session_id})
        runtime_node = self._runtime().api_runtime_node
        invocation = runtime_node.resolve_session_detail_invocation(session_id)
        runtime_engine = self._runtime().engine
        session = await invoke_api_method(runtime_engine.sessions, invocation, "session")
        if not session:
            interaction_session = await self._runtime().interaction_manager.queries.get_session_detail(session_id)
            if interaction_session is not None:
                return interaction_session
            raise HTTPException(**runtime_node.session_detail_not_found_error(session_id))
        return session

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        runtime_node = self._runtime().api_runtime_node
        runtime_engine = self._runtime().engine
        session = await runtime_engine.sessions.get_session(session_id)
        if not session:
            interaction_status = await self._runtime().interaction_manager.queries.get_session_status(session_id)
            if interaction_status is not None:
                return cast(dict[str, Any], interaction_status)
            raise HTTPException(**runtime_node.session_detail_not_found_error(session_id))

        run_record = await runtime_engine.run_ledger.get_run(session_id)
        projected_run_record = validated_run_ledger_record_projection(run_record)
        backlog = await runtime_engine.sessions.get_session_issues(session_id)
        tasks = await self._runtime().runtime_state.get_tasks(session_id)
        is_active, task_state = _runtime_task_summary(tasks)

        backlog_counts: dict[str, int] = {}
        for issue in backlog:
            issue_status = str(issue.get("status") or "unknown")
            backlog_counts[issue_status] = backlog_counts.get(issue_status, 0) + 1
        return {
            "session_id": session_id,
            "active": is_active,
            "status": (projected_run_record or {}).get("status", session.get("status")),
            "task_state": task_state,
            "backlog": {
                "count": len(backlog),
                "by_status": backlog_counts,
            },
            "summary": dict((projected_run_record or {}).get("summary_json") or {}),
            "artifacts": dict((projected_run_record or {}).get("artifact_json") or {}),
        }

    async def halt_session(self, session_id: str, request: Request) -> dict[str, Any]:
        runtime_engine = self._runtime().engine
        run_record = await runtime_engine.run_ledger.get_run(session_id)
        if run_record is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        await runtime_engine.halt_session(
            session_id,
            operator_actor_ref=getattr(request.state, "authenticated_actor_ref", None),
        )
        tasks = await self._runtime().runtime_state.get_tasks(session_id)
        is_active, _task_state = _runtime_task_summary(tasks)
        return {
            "ok": True,
            "session_id": session_id,
            "active": is_active,
        }

    async def replay_session_turn(
        self,
        session_id: str,
        issue_id: str | None = None,
        turn_index: int | None = Query(default=None, ge=1),
        role: str | None = None,
    ) -> Any:
        runtime_engine = self._runtime().engine
        run_record = await runtime_engine.run_ledger.get_run(session_id)
        session = await runtime_engine.sessions.get_session(session_id)
        if not issue_id and turn_index is None:
            if run_record is None and session is None:
                interaction_timeline = await self._runtime().interaction_manager.queries.get_session_replay_timeline(
                    session_id,
                    role=role,
                )
                if interaction_timeline is not None:
                    return interaction_timeline
                raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
            return await read_run_replay_turns(self._runtime, session_id, role)
        if not issue_id or turn_index is None:
            raise HTTPException(
                status_code=422,
                detail="Both 'issue_id' and 'turn_index' are required for targeted replay.",
            )
        if run_record is None and session is None:
            interaction_session = await self._runtime().interaction_manager.queries.get_session_detail(session_id)
            if interaction_session is not None:
                raise HTTPException(
                    status_code=422,
                    detail="Targeted replay is not supported for interaction sessions.",
                )
        try:
            replay = await read_runtime_replay(
                runtime_engine,
                session_id=session_id,
                issue_id=str(issue_id),
                turn_index=turn_index,
                role=role,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return replay

    async def get_session_snapshot(self, session_id: str) -> Any:
        await self._runtime().events.emit("api_session_snapshot", {"session_id": session_id})
        runtime_node = self._runtime().api_runtime_node
        invocation = runtime_node.resolve_session_snapshot_invocation(session_id)
        runtime_engine = self._runtime().engine
        snapshot = await invoke_api_method(runtime_engine.snapshots, invocation, "snapshot")
        if not snapshot:
            interaction_snapshot = await self._runtime().interaction_manager.queries.get_session_snapshot(session_id)
            if interaction_snapshot is not None:
                return interaction_snapshot
            raise HTTPException(**runtime_node.session_snapshot_not_found_error(session_id))
        return snapshot

def build_session_history_router(*, runtime_getter) -> APIRouter:
    router = APIRouter()
    endpoints = SessionHistoryEndpoints(runtime_getter)
    router.add_api_route("/sessions/{session_id}", endpoints.get_session_detail, methods=["GET"])
    router.add_api_route("/sessions/{session_id}/status", endpoints.get_session_status, methods=["GET"])
    router.add_api_route("/sessions/{session_id}/halt", endpoints.halt_session, methods=["POST"])
    router.add_api_route("/sessions/{session_id}/replay", endpoints.replay_session_turn, methods=["GET"])
    router.add_api_route("/sessions/{session_id}/snapshot", endpoints.get_session_snapshot, methods=["GET"])
    return router
