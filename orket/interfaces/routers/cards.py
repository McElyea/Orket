from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.interfaces.operator_view_models import (
    build_card_detail_view,
    build_card_list_item_view,
    build_run_detail_view,
    card_view_matches_filter,
)


class ArchiveCardsRequest(BaseModel):
    card_ids: list[str] | None = None
    build_id: str | None = None
    related_tokens: list[str] | None = None
    reason: str | None = None
    archived_by: str | None = "api"


def _parse_guard_status_from_action(action: str) -> str | None:
    action_text = str(action or "")
    marker = "Set Status to '"
    start = action_text.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = action_text.find("'", start)
    if end < 0:
        return None
    status = action_text[start:end].strip().lower()
    guard_statuses = {
        "awaiting_guard_review",
        "guard_approved",
        "guard_rejected",
        "guard_requested_changes",
    }
    if status in guard_statuses:
        return status
    return None


def build_cards_router(engine_getter: Callable[[], Any], api_runtime_node_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    async def _load_run_view_for_session(*, engine: Any, session_id: str) -> dict[str, Any] | None:
        normalized_session_id = str(session_id or "").strip()
        if not normalized_session_id:
            return None
        run_record = await engine.run_ledger.get_run(normalized_session_id)
        session = await engine.sessions.get_session(normalized_session_id)
        if run_record is None and session is None:
            return None
        backlog = await engine.sessions.get_session_issues(normalized_session_id)
        projected_run_record = validated_run_ledger_record_projection(run_record)
        summary = dict(projected_run_record.get("summary_json") or {}) if isinstance(projected_run_record, dict) else {}
        artifacts = dict(projected_run_record.get("artifact_json") or {}) if isinstance(projected_run_record, dict) else {}
        status = projected_run_record.get("status") if isinstance(projected_run_record, dict) else None
        if status is None and isinstance(session, dict):
            status = session.get("status")
        return build_run_detail_view(
            session_id=normalized_session_id,
            status=status,
            summary=summary,
            artifacts=artifacts,
            issue_count=len(backlog),
        )

    @router.get("/cards")
    async def list_cards(
        build_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        engine = engine_getter()
        cards = await engine.cards.list_cards(
            build_id=build_id,
            session_id=session_id,
            status=status,
            limit=limit,
            offset=offset,
        )
        return {
            "items": cards,
            "limit": limit,
            "offset": offset,
            "count": len(cards),
            "filters": {
                "build_id": build_id,
                "session_id": session_id,
                "status": status,
            },
        }

    @router.get("/cards/view")
    async def list_card_views(
        build_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        filter: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        engine = engine_getter()
        cards = await engine.cards.list_cards(
            build_id=build_id,
            session_id=session_id,
            status=status,
            limit=500 if filter else limit,
            offset=0 if filter else offset,
        )
        session_views: dict[str, dict[str, Any] | None] = {}
        items: list[dict[str, Any]] = []
        for card in cards:
            card_payload = card.model_dump() if hasattr(card, "model_dump") else dict(card)
            card_session_id = str(card_payload.get("session_id") or "").strip()
            if card_session_id not in session_views:
                session_views[card_session_id] = await _load_run_view_for_session(engine=engine, session_id=card_session_id)
            view = build_card_list_item_view(card=card_payload, run_view=session_views[card_session_id])
            if card_view_matches_filter(view, filter):
                items.append(view)
        page = items[offset : offset + limit]
        return {
            "items": page,
            "limit": limit,
            "offset": offset,
            "count": len(page),
            "total": len(items),
            "filters": {
                "build_id": build_id,
                "session_id": session_id,
                "status": status,
                "filter": filter,
            },
        }

    @router.get("/cards/{card_id}/view")
    async def get_card_view(card_id: str) -> dict[str, Any]:
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        history = await engine.cards.get_card_history(card_id)
        comments = await engine.cards.get_comments(card_id)
        card_payload = card.model_dump() if hasattr(card, "model_dump") else dict(card)
        run_view = await _load_run_view_for_session(engine=engine, session_id=str(card_payload.get("session_id") or ""))
        return build_card_detail_view(
            card=card_payload,
            history=history,
            comments=comments,
            run_view=run_view,
        )

    @router.get("/cards/{card_id}")
    async def get_card_detail(card_id: str) -> Any:
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        if hasattr(card, "model_dump"):
            return card.model_dump()
        return card

    @router.get("/cards/{card_id}/history")
    async def get_card_history(card_id: str) -> dict[str, Any]:
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        history = await engine.cards.get_card_history(card_id)
        return {"card_id": card_id, "history": history}

    @router.get("/cards/{card_id}/guard-history")
    async def get_card_guard_history(card_id: str) -> dict[str, Any]:
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        history = await engine.cards.get_card_history(card_id)

        items: list[dict[str, Any]] = []
        summary = {
            "awaiting_guard_review": 0,
            "guard_approved": 0,
            "guard_rejected": 0,
            "guard_requested_changes": 0,
            "retry_count": 0,
            "terminal_failures": 0,
        }

        for entry in history:
            text = str(entry or "")
            guard_status = _parse_guard_status_from_action(text)
            if not guard_status and "terminal_failure" not in text.lower():
                continue

            timestamp = None
            actor = None
            action = text
            if ": " in text and " -> " in text:
                timestamp, remainder = text.split(": ", 1)
                if " -> " in remainder:
                    actor, action = remainder.split(" -> ", 1)

            terminal = "terminal_failure" in text.lower()
            if guard_status:
                summary[guard_status] += 1
                if guard_status in {"guard_rejected", "guard_requested_changes"}:
                    summary["retry_count"] += 1
            if terminal:
                summary["terminal_failures"] += 1

            items.append(
                {
                    "timestamp": timestamp,
                    "actor": actor,
                    "action": action,
                    "guard_status": guard_status,
                    "terminal_failure": terminal,
                }
            )

        return {
            "card_id": card_id,
            "count": len(items),
            "items": items,
            "summary": summary,
        }

    @router.get("/cards/{card_id}/comments")
    async def get_card_comments(card_id: str) -> dict[str, Any]:
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        comments = await engine.cards.get_comments(card_id)
        return {"card_id": card_id, "comments": comments}

    @router.post("/cards/archive")
    async def archive_cards(req: ArchiveCardsRequest) -> Any:
        engine = engine_getter()
        api_runtime_node = api_runtime_node_getter()
        if not api_runtime_node.has_archive_selector(req.card_ids, req.build_id, req.related_tokens):
            raise HTTPException(status_code=400, detail=api_runtime_node.archive_selector_missing_detail())

        archived_ids: list[str] = []
        missing_ids: list[str] = []
        archived_count = 0
        archived_by = req.archived_by or "api"

        if req.card_ids:
            result = await engine.archive_cards(req.card_ids, archived_by=archived_by, reason=req.reason)
            archived_ids.extend(result.get("archived", []))
            missing_ids.extend(result.get("missing", []))

        if req.build_id:
            count = await engine.archive_build(req.build_id, archived_by=archived_by, reason=req.reason)
            archived_count += count

        if req.related_tokens:
            result = await engine.archive_related_cards(req.related_tokens, archived_by=archived_by, reason=req.reason)
            archived_ids.extend(result.get("archived", []))
            missing_ids.extend(result.get("missing", []))

        return api_runtime_node.normalize_archive_response(
            archived_ids=archived_ids,
            missing_ids=missing_ids,
            archived_count=archived_count,
        )

    return router
