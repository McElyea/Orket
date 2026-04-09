from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.interfaces.operator_view_models import build_run_detail_view, build_run_history_item_view


def build_runs_router(engine_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    async def _load_run_projection(session_id: str) -> dict[str, Any]:
        engine = engine_getter()
        run_record = await engine.run_ledger.get_run(session_id)
        session = await engine.sessions.get_session(session_id)
        if run_record is None and session is None:
            raise HTTPException(status_code=404, detail=f"Run '{session_id}' not found")
        backlog = await engine.sessions.get_session_issues(session_id)
        projected_run_record = validated_run_ledger_record_projection(run_record)
        summary = dict(projected_run_record.get("summary_json") or {}) if isinstance(projected_run_record, dict) else {}
        artifacts = dict(projected_run_record.get("artifact_json") or {}) if isinstance(projected_run_record, dict) else {}
        status = projected_run_record.get("status") if isinstance(projected_run_record, dict) else None
        if status is None and isinstance(session, dict):
            status = session.get("status")
        return {
            "session_id": session_id,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
            "issue_count": len(backlog),
        }

    @router.get("/runs/view")
    async def list_run_views(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        engine = engine_getter()
        recent_runs = await engine.sessions.get_recent_runs(limit=limit)
        items: list[dict[str, Any]] = []
        for row in recent_runs:
            session_id = str((row or {}).get("id") or (row or {}).get("session_id") or "").strip()
            if not session_id:
                continue
            projection = await _load_run_projection(session_id)
            items.append(
                build_run_history_item_view(
                    session_id=session_id,
                    status=projection["status"],
                    summary=projection["summary"],
                    artifacts=projection["artifacts"],
                    issue_count=projection["issue_count"],
                )
            )
        return {
            "items": items,
            "count": len(items),
            "limit": limit,
        }

    @router.get("/runs/{session_id}/view")
    async def get_run_view(session_id: str) -> dict[str, Any]:
        projection = await _load_run_projection(session_id)
        return build_run_detail_view(
            session_id=session_id,
            status=projection["status"],
            summary=projection["summary"],
            artifacts=projection["artifacts"],
            issue_count=projection["issue_count"],
        )

    return router
