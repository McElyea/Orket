from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel


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


def build_cards_router(engine_getter: Callable[[], Any], api_runtime_node: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/cards")
    async def list_cards(
        build_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
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

    @router.get("/cards/{card_id}")
    async def get_card_detail(card_id: str):
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        if hasattr(card, "model_dump"):
            return card.model_dump()
        return card

    @router.get("/cards/{card_id}/history")
    async def get_card_history(card_id: str):
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        history = await engine.cards.get_card_history(card_id)
        return {"card_id": card_id, "history": history}

    @router.get("/cards/{card_id}/guard-history")
    async def get_card_guard_history(card_id: str):
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
    async def get_card_comments(card_id: str):
        engine = engine_getter()
        card = await engine.cards.get_by_id(card_id)
        if card is None:
            raise HTTPException(status_code=404, detail=f"Card '{card_id}' not found")
        comments = await engine.cards.get_comments(card_id)
        return {"card_id": card_id, "comments": comments}

    @router.post("/cards/archive")
    async def archive_cards(req: ArchiveCardsRequest):
        engine = engine_getter()
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
