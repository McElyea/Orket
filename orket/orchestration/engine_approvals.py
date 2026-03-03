from __future__ import annotations

import os
from typing import Any, Optional

from orket.kernel.v1.nervous_system_runtime_extensions import (
    decide_approval_v1,
    get_approval_v1,
    list_approvals_v1,
)


def _api_approval_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "pending": "PENDING",
        "approved": "APPROVED",
        "denied": "DENIED",
        "approved_with_edits": "APPROVED_WITH_EDITS",
        "expired": "EXPIRED",
    }
    return mapping.get(normalized, "PENDING")


def _repo_approval_status(value: str) -> str:
    mapping = {
        "PENDING": "pending",
        "APPROVED": "approved",
        "DENIED": "denied",
        "APPROVED_WITH_EDITS": "approved_with_edits",
        "EXPIRED": "expired",
    }
    normalized = str(value or "").strip().upper()
    if normalized not in mapping:
        raise ValueError("status must be one of PENDING, APPROVED, DENIED, APPROVED_WITH_EDITS, EXPIRED")
    return mapping[normalized]


def _normalize_approval_row(row: dict[str, Any]) -> dict[str, Any]:
    approval_id = str(row.get("request_id") or "").strip()
    return {
        "approval_id": approval_id,
        "request_id": approval_id,
        "session_id": str(row.get("session_id") or ""),
        "issue_id": str(row.get("issue_id") or ""),
        "seat_name": str(row.get("seat_name") or ""),
        "gate_mode": str(row.get("gate_mode") or ""),
        "request_type": str(row.get("request_type") or ""),
        "reason": str(row.get("reason") or ""),
        "payload": dict(row.get("payload_json") or {}),
        "status": _api_approval_status(row.get("status")),
        "resolution": dict(row.get("resolution_json") or {}),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "resolved_at": str(row.get("resolved_at") or ""),
    }


def _nervous_system_enabled() -> bool:
    raw = str(os.environ.get("ORKET_ENABLE_NERVOUS_SYSTEM") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


async def list_approvals(
    engine: Any,
    *,
    session_id: Optional[str] = None,
    status: Optional[str] = None,
    request_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if _nervous_system_enabled():
        return list_approvals_v1(
            status=status,
            session_id=session_id,
            request_id=request_id,
            limit=limit,
        )

    repo_status = None
    if status:
        repo_status = _repo_approval_status(status)
    rows = await engine.pending_gates.list_requests(
        session_id=session_id,
        status=repo_status,
        limit=max(1, int(limit)),
    )
    items = [_normalize_approval_row(row) for row in rows]
    normalized_request_id = str(request_id or "").strip()
    if normalized_request_id:
        items = [item for item in items if item["approval_id"] == normalized_request_id]
    return items


async def get_approval(engine: Any, approval_id: str) -> Optional[dict[str, Any]]:
    if _nervous_system_enabled():
        return get_approval_v1(approval_id)

    normalized_id = str(approval_id or "").strip()
    if not normalized_id:
        return None
    rows = await engine.pending_gates.list_requests(limit=1000)
    for row in rows:
        if str(row.get("request_id") or "").strip() == normalized_id:
            return _normalize_approval_row(row)
    return None


async def decide_approval(
    engine: Any,
    *,
    approval_id: str,
    decision: str,
    edited_proposal: Optional[dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    if _nervous_system_enabled():
        return decide_approval_v1(
            approval_id=approval_id,
            decision=decision,
            edited_proposal=edited_proposal,
            notes=notes,
        )

    existing = await get_approval(engine, approval_id)
    if not existing:
        raise ValueError("approval not found")

    decision_token = str(decision or "").strip().lower()
    decision_map = {
        "approve": "APPROVED",
        "deny": "DENIED",
        "edit": "APPROVED_WITH_EDITS",
        "expire": "EXPIRED",
    }
    target_status = decision_map.get(decision_token)
    if not target_status:
        raise ValueError("decision must be one of: approve, deny, edit, expire")

    resolution: dict[str, Any] = {"decision": decision_token}
    if edited_proposal is not None:
        resolution["edited_proposal"] = edited_proposal
    note_text = str(notes or "").strip()
    if note_text:
        resolution["notes"] = note_text

    current_status = existing["status"]
    current_resolution = dict(existing.get("resolution") or {})
    if current_status != "PENDING":
        if current_status == target_status and current_resolution == resolution:
            return {"status": "idempotent", "approval": existing}
        raise RuntimeError("approval already resolved with a conflicting decision")

    await engine.pending_gates.resolve_request(
        request_id=approval_id,
        status=_repo_approval_status(target_status),
        resolution=resolution,
    )
    updated = await get_approval(engine, approval_id)
    if not updated:
        raise RuntimeError("approval resolution persisted but lookup failed")
    return {"status": "resolved", "approval": updated}


__all__ = ["decide_approval", "get_approval", "list_approvals"]
