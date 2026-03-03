from __future__ import annotations

from typing import Any, Callable

from .canonical import digest_of
from .nervous_system_runtime_state import (
    _APPROVALS_BY_ID,
    _LEDGER_BY_SESSION,
    _PENDING_APPROVALS_CACHE,
    _RUNTIME_LOCK,
    append_event,
    utc_iso_now,
)

APPROVAL_STATUSES = (
    "PENDING",
    "APPROVED",
    "DENIED",
    "APPROVED_WITH_EDITS",
    "EXPIRED",
)

_DECISION_TO_STATUS = {
    "approve": "APPROVED",
    "deny": "DENIED",
    "edit": "APPROVED_WITH_EDITS",
    "expire": "EXPIRED",
}


def _approval_id(session_id: str, proposal_digest: str, decision_digest: str) -> str:
    return f"apr-{digest_of({'session_id': session_id, 'proposal_digest': proposal_digest, 'decision_digest': decision_digest})[:16]}"


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return "PENDING"
    if normalized not in APPROVAL_STATUSES:
        raise ValueError("status must be one of PENDING, APPROVED, DENIED, APPROVED_WITH_EDITS, EXPIRED")
    return normalized


def _normalize_decision(decision: str) -> str:
    key = str(decision or "").strip().lower()
    status = _DECISION_TO_STATUS.get(key)
    if not status:
        raise ValueError("decision must be one of: approve, deny, edit, expire")
    return status


def create_approval_request(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    proposal_digest: str,
    decision_digest: str,
    reason_codes: list[str],
) -> dict[str, Any]:
    approval_id = _approval_id(session_id, proposal_digest, decision_digest)
    now = utc_iso_now()

    with _RUNTIME_LOCK:
        existing = _APPROVALS_BY_ID.get(approval_id)
        if existing is not None:
            return dict(existing)

        approval = {
            "approval_id": approval_id,
            "request_id": approval_id,
            "session_id": session_id,
            "trace_id": trace_id,
            "request_ref": request_id,
            "proposal_digest": proposal_digest,
            "admission_decision_digest": decision_digest,
            "reason_codes": list(reason_codes),
            "status": "PENDING",
            "resolution": {},
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
        }
        _APPROVALS_BY_ID[approval_id] = approval

    append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="approval.requested",
        body={
            "approval_id": approval_id,
            "proposal_digest": proposal_digest,
            "decision_digest": decision_digest,
            "reason_codes": list(reason_codes),
        },
    )
    rebuild_pending_approvals(session_id)
    return dict(approval)


def rebuild_pending_approvals(session_id: str) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    with _RUNTIME_LOCK:
        events = list(_LEDGER_BY_SESSION.get(session_id, []))
        rebuilt: dict[str, dict[str, Any]] = {}
        for event in events:
            body = event.get("body")
            if not isinstance(body, dict):
                continue

            if event.get("event_type") == "approval.requested":
                approval_id = str(body.get("approval_id") or "").strip()
                if not approval_id:
                    continue
                existing = _APPROVALS_BY_ID.get(approval_id)
                base = {
                    "approval_id": approval_id,
                    "request_id": approval_id,
                    "session_id": session_id,
                    "trace_id": str(event.get("trace_id") or ""),
                    "request_ref": event.get("request_id"),
                    "proposal_digest": str(body.get("proposal_digest") or ""),
                    "admission_decision_digest": str(body.get("decision_digest") or ""),
                    "reason_codes": list(body.get("reason_codes") or []),
                    "status": "PENDING",
                    "resolution": {},
                    "created_at": str(event.get("created_at") or ""),
                    "updated_at": str(event.get("created_at") or ""),
                    "resolved_at": None,
                }
                if isinstance(existing, dict):
                    base.update(
                        {
                            "status": str(existing.get("status") or "PENDING"),
                            "resolution": dict(existing.get("resolution") or {}),
                            "updated_at": str(existing.get("updated_at") or base["updated_at"]),
                            "resolved_at": existing.get("resolved_at"),
                        }
                    )
                rebuilt[approval_id] = base

            if event.get("event_type") == "approval.decided":
                approval_id = str(body.get("approval_id") or "").strip()
                if not approval_id:
                    continue
                current = rebuilt.get(approval_id) or dict(_APPROVALS_BY_ID.get(approval_id) or {})
                if not current:
                    continue
                current["status"] = _normalize_status(str(body.get("status") or "PENDING"))
                current["resolution"] = dict(body.get("resolution") or {})
                current["updated_at"] = str(event.get("created_at") or current.get("updated_at") or "")
                if current["status"] != "PENDING":
                    current["resolved_at"] = current["updated_at"]
                rebuilt[approval_id] = current

        for approval_id, record in rebuilt.items():
            _APPROVALS_BY_ID[approval_id] = record
            if str(record.get("status") or "") == "PENDING":
                pending.append(dict(record))
        _PENDING_APPROVALS_CACHE[session_id] = sorted(
            pending,
            key=lambda row: (str(row.get("created_at") or ""), str(row.get("approval_id") or "")),
            reverse=True,
        )

    return [dict(row) for row in _PENDING_APPROVALS_CACHE.get(session_id, [])]


def list_approvals(
    *,
    status: str | None,
    session_id: str | None,
    request_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    status_filter = _normalize_status(status) if status else None
    request_filter = str(request_id or "").strip()

    with _RUNTIME_LOCK:
        if session_id:
            rebuild_pending_approvals(session_id)
        else:
            for sid in sorted(_LEDGER_BY_SESSION.keys()):
                rebuild_pending_approvals(sid)

        rows = [dict(item) for item in _APPROVALS_BY_ID.values()]

    if session_id:
        rows = [row for row in rows if row.get("session_id") == session_id]
    if status_filter:
        rows = [row for row in rows if row.get("status") == status_filter]
    if request_filter:
        rows = [row for row in rows if str(row.get("request_ref") or "") == request_filter]

    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("approval_id") or "")), reverse=True)
    return rows[: max(1, int(limit))]


def get_approval(approval_id: str) -> dict[str, Any] | None:
    normalized = str(approval_id or "").strip()
    if not normalized:
        return None
    with _RUNTIME_LOCK:
        row = _APPROVALS_BY_ID.get(normalized)
        return dict(row) if row is not None else None


def decide_approval(
    *,
    approval_id: str,
    decision: str,
    edited_proposal: dict[str, Any] | None,
    notes: str | None,
    readmit_edited_proposal: Callable[[str, str, str | None, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_id = str(approval_id or "").strip()
    if not normalized_id:
        raise ValueError("approval not found")

    target_status = _normalize_decision(decision)
    note_text = str(notes or "").strip()
    resolution: dict[str, Any] = {"decision": str(decision or "").strip().lower()}
    if edited_proposal is not None:
        resolution["edited_proposal"] = dict(edited_proposal)
    if note_text:
        resolution["notes"] = note_text

    with _RUNTIME_LOCK:
        existing = _APPROVALS_BY_ID.get(normalized_id)
        if not existing:
            raise ValueError("approval not found")

        current_status = _normalize_status(str(existing.get("status") or "PENDING"))
        current_resolution = dict(existing.get("resolution") or {})

        if current_status != "PENDING":
            if current_status == target_status and current_resolution == resolution:
                return {"status": "idempotent", "approval": dict(existing)}
            raise RuntimeError("approval already resolved with a conflicting decision")

        now = utc_iso_now()
        existing["status"] = target_status
        existing["resolution"] = dict(resolution)
        existing["updated_at"] = now
        if target_status != "PENDING":
            existing["resolved_at"] = now
        _APPROVALS_BY_ID[normalized_id] = existing

    append_event(
        session_id=str(existing.get("session_id") or ""),
        trace_id=str(existing.get("trace_id") or ""),
        request_id=existing.get("request_ref"),
        event_type="approval.decided",
        body={
            "approval_id": normalized_id,
            "proposal_digest": str(existing.get("proposal_digest") or ""),
            "decision_digest": str(existing.get("admission_decision_digest") or ""),
            "status": target_status,
            "resolution": dict(resolution),
        },
    )

    followup = None
    if target_status == "APPROVED_WITH_EDITS":
        if edited_proposal is None or not isinstance(edited_proposal, dict):
            raise ValueError("edited_proposal is required when decision=edit")
        if readmit_edited_proposal is not None:
            followup = readmit_edited_proposal(
                str(existing.get("session_id") or ""),
                str(existing.get("trace_id") or ""),
                existing.get("request_ref"),
                edited_proposal,
            )
            if isinstance(followup, dict):
                resolution["edited_proposal_digest"] = str(followup.get("proposal_digest") or "")

    rebuild_pending_approvals(str(existing.get("session_id") or ""))
    response = {"status": "resolved", "approval": dict(_APPROVALS_BY_ID[normalized_id])}
    if followup is not None:
        response["next_admission"] = followup
    return response


__all__ = [
    "APPROVAL_STATUSES",
    "create_approval_request",
    "decide_approval",
    "get_approval",
    "list_approvals",
    "rebuild_pending_approvals",
]
