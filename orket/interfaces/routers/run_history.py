"""API transport over the existing application query and lifetime owners."""
from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException

from orket.application.services.api_run_query_service import ApiRunQueryService
from orket.application.services.execution_graph_service import (
    execution_graph_payload,
    inspect_execution_graph,
    persist_execution_graph_snapshot,
)
from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.interfaces.api_invocation import invoke_api_method


async def read_run_replay_turns(runtime_getter, session_id: str, role: str | None = None) -> dict[str, Any]:
    runtime_engine = runtime_getter().engine
    run_record = await runtime_engine.run_ledger.get_run(session_id)
    session = await runtime_engine.sessions.get_session(session_id)
    if run_record is None and session is None:
        raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
    try:
        turns = await runtime_getter().run_queries.replay_turns(session_id, role)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "session_id": session_id,
        "turn_count": len(turns),
        "filters": {"role": role or None},
        "turns": turns,
    }


class RunHistoryEndpoints:
    def __init__(self, runtime_getter, outbound_filter):
        self._runtime, self._filter = runtime_getter, outbound_filter

    async def get_run_detail(self, session_id: str) -> dict[str, Any]:
        outward_record = await self._runtime().outward_run_service.get_status(session_id)
        if outward_record is not None:
            return cast(dict[str, Any], self._filter(
                await self._runtime().outward_run_service.status_payload(outward_record.run_id), surface="api.runs.status"))

        runtime_engine = self._runtime().engine
        run_record = await runtime_engine.run_ledger.get_run(session_id)
        session = await runtime_engine.sessions.get_session(session_id)

        if run_record is None and session is None:
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

        backlog = await runtime_engine.sessions.get_session_issues(session_id)
        summary = {}
        artifacts = {}
        status = None
        projected_run_record = validated_run_ledger_record_projection(run_record)
        if isinstance(projected_run_record, dict):
            summary = dict(projected_run_record.get("summary_json") or {})
            artifacts = dict(projected_run_record.get("artifact_json") or {})
            status = projected_run_record.get("status")
        if status is None and isinstance(session, dict):
            status = session.get("status")

        payload = {
            "session_id": session_id,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
            "issue_count": len(backlog),
            "session": session,
            "run_ledger": projected_run_record,
        }
        return cast(dict[str, Any], self._filter(payload, surface="api.runs.status"))

    async def get_run_metrics(self, session_id: str) -> Any:
        await self._runtime().events.emit("api_run_metrics", {"session_id": session_id})
        metrics_reader = self._runtime().api_runtime_host.create_member_metrics_reader()
        try:
            return await self._runtime().system_queries.member_metrics(session_id, metrics_reader)
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    async def get_run_token_summary(self, session_id: str) -> dict[str, Any]:
        runtime_engine = self._runtime().engine
        run_record = await runtime_engine.run_ledger.get_run(session_id)
        session = await runtime_engine.sessions.get_session(session_id)
        if run_record is None and session is None:
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

        try:
            return await cast(ApiRunQueryService, self._runtime().run_queries).token_summary(session_id)
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    async def list_run_replay_turns(self, session_id: str, role: str | None = None) -> dict[str, Any]:
        return await read_run_replay_turns(self._runtime, session_id, role)

    async def get_backlog(self, session_id: str) -> Any:
        await self._runtime().events.emit("api_backlog", {"session_id": session_id})
        invocation = self._runtime().api_runtime_node.resolve_backlog_invocation(session_id)
        runtime_engine = self._runtime().engine
        return await invoke_api_method(runtime_engine.sessions, invocation, "backlog")

    async def get_execution_graph(self, session_id: str) -> dict[str, Any]:
        runtime_engine = self._runtime().engine
        run_record = await runtime_engine.run_ledger.get_run(session_id)
        session = await runtime_engine.sessions.get_session(session_id)
        if run_record is None and session is None:
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")

        graph = await inspect_execution_graph(cards=runtime_engine.cards, session_id=session_id)
        index = {node["id"]: node["order_index"] for node in graph["nodes"]}
        try:
            handoffs = await self._runtime().run_queries.handoffs(session_id, index)
            run_path = await self._runtime().run_queries.run_path(session_id)
        except PermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload = execution_graph_payload(session_id=session_id, graph=graph, handoffs=handoffs)
        await persist_execution_graph_snapshot(cards=runtime_engine.cards, run_path=run_path, payload=payload)
        return payload

def build_run_history_router(*, runtime_getter, outbound_filter) -> APIRouter:
    router = APIRouter()
    endpoints = RunHistoryEndpoints(runtime_getter, outbound_filter)
    router.add_api_route("/runs/{session_id}", endpoints.get_run_detail, methods=["GET"])
    router.add_api_route("/runs/{session_id}/metrics", endpoints.get_run_metrics, methods=["GET"])
    router.add_api_route("/runs/{session_id}/token-summary", endpoints.get_run_token_summary, methods=["GET"])
    router.add_api_route("/runs/{session_id}/replay", endpoints.list_run_replay_turns, methods=["GET"])
    router.add_api_route("/runs/{session_id}/backlog", endpoints.get_backlog, methods=["GET"])
    router.add_api_route("/runs/{session_id}/execution-graph", endpoints.get_execution_graph, methods=["GET"])
    return router
