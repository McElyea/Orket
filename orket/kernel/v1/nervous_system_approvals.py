from __future__ import annotations

from copy import deepcopy
from typing import Any

from orket.application.services.kernel_runtime_owner import current_kernel_runtime

from .canonical import digest_of
from .nervous_system_runtime_state import append_event

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
}


def _approval_id(session_id: str, proposal_digest: str, decision_digest: str) -> str:
    digest = digest_of(
        {
            "session_id": session_id,
            "proposal_digest": proposal_digest,
            "decision_digest": decision_digest,
        }
    )
    return f"apr-{digest[:16]}"


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
        raise ValueError("decision must be one of: approve, deny")
    return status


def create_approval_request(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    proposal_digest: str,
    decision_digest: str,
    reason_codes: list[str],
    created_at: str,
) -> dict[str, Any]:
    owner = current_kernel_runtime()
    reason_codes = deepcopy(reason_codes)
    approval_id = _approval_id(session_id, proposal_digest, decision_digest)
    now = created_at

    with owner.lock:
        existing = owner.approvals_by_id.get(approval_id)
        if existing is not None:
            return deepcopy(existing)

        approval: dict[str, Any] = {
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
        owner.approvals_by_id[approval_id] = approval

        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="approval.requested",
            created_at=now,
            body={
                "approval_id": approval_id,
                "proposal_digest": proposal_digest,
                "decision_digest": decision_digest,
                "reason_codes": list(reason_codes),
            },
        )
        rebuild_pending_approvals(session_id)
        return deepcopy(approval)


def rebuild_pending_approvals(session_id: str) -> list[dict[str, Any]]:
    owner = current_kernel_runtime()
    pending: list[dict[str, Any]] = []
    with owner.lock:
        events = list(owner.ledger_by_session.get(session_id, []))
        rebuilt: dict[str, dict[str, Any]] = {}
        for event in events:
            body = event.get("body")
            if not isinstance(body, dict):
                continue

            if event.get("event_type") == "approval.requested":
                approval_id = str(body.get("approval_id") or "").strip()
                if not approval_id:
                    continue
                existing = owner.approvals_by_id.get(approval_id)
                base: dict[str, Any] = {
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
                            "resolution": deepcopy(existing.get("resolution") or {}),
                            "updated_at": str(existing.get("updated_at") or base["updated_at"]),
                            "resolved_at": existing.get("resolved_at"),
                        }
                    )
                rebuilt[approval_id] = base

            if event.get("event_type") == "approval.decided":
                approval_id = str(body.get("approval_id") or "").strip()
                if not approval_id:
                    continue
                current = rebuilt.get(approval_id) or deepcopy(owner.approvals_by_id.get(approval_id) or {})
                if not current:
                    continue
                current["status"] = _normalize_status(str(body.get("status") or "PENDING"))
                current["resolution"] = deepcopy(body.get("resolution") or {})
                current["updated_at"] = str(event.get("created_at") or current.get("updated_at") or "")
                if current["status"] != "PENDING":
                    current["resolved_at"] = current["updated_at"]
                rebuilt[approval_id] = current

        for approval_id, record in rebuilt.items():
            owner.approvals_by_id[approval_id] = record
            if str(record.get("status") or "") == "PENDING":
                pending.append(deepcopy(record))
        owner.pending_approvals_cache[session_id] = sorted(
            pending,
            key=lambda row: (str(row.get("created_at") or ""), str(row.get("approval_id") or "")),
            reverse=True,
        )

        return deepcopy(owner.pending_approvals_cache.get(session_id, []))


def list_approvals(
    *,
    status: str | None,
    session_id: str | None,
    request_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    owner = current_kernel_runtime()
    status_filter = _normalize_status(status) if status else None
    request_filter = str(request_id or "").strip()

    with owner.lock:
        if session_id:
            rebuild_pending_approvals(session_id)
        else:
            for sid in sorted(owner.ledger_by_session.keys()):
                rebuild_pending_approvals(sid)

        rows = [deepcopy(item) for item in owner.approvals_by_id.values()]

    if session_id:
        rows = [row for row in rows if row.get("session_id") == session_id]
    if status_filter:
        rows = [row for row in rows if row.get("status") == status_filter]
    if request_filter:
        rows = [row for row in rows if str(row.get("request_ref") or "") == request_filter]

    rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("approval_id") or "")), reverse=True)
    return rows[: max(1, int(limit))]


def get_approval(approval_id: str) -> dict[str, Any] | None:
    owner = current_kernel_runtime()
    normalized = str(approval_id or "").strip()
    if not normalized:
        return None
    with owner.lock:
        row = owner.approvals_by_id.get(normalized)
        return deepcopy(row) if row is not None else None


def decide_approval(
    *,
    approval_id: str,
    decision: str,
    edited_proposal: dict[str, Any] | None,
    notes: str | None,
    observed_at: str,
) -> dict[str, Any]:
    owner = current_kernel_runtime()
    normalized_id = str(approval_id or "").strip()
    if not normalized_id:
        raise ValueError("approval not found")

    target_status = _normalize_decision(decision)
    note_text = str(notes or "").strip()
    resolution: dict[str, Any] = {"decision": str(decision or "").strip().lower()}
    if edited_proposal is not None:
        resolution["edited_proposal"] = deepcopy(edited_proposal)
    if note_text:
        resolution["notes"] = note_text

    with owner.lock:
        existing = owner.approvals_by_id.get(normalized_id)
        if not existing:
            raise ValueError("approval not found")

        current_status = _normalize_status(str(existing.get("status") or "PENDING"))
        current_resolution = deepcopy(existing.get("resolution") or {})

        if current_status != "PENDING":
            if current_status == target_status and current_resolution == resolution:
                return {"status": "idempotent", "approval": deepcopy(existing)}
            raise RuntimeError("approval already resolved with a conflicting decision")

        now = observed_at
        existing["status"] = target_status
        existing["resolution"] = deepcopy(resolution)
        existing["updated_at"] = now
        if target_status != "PENDING":
            existing["resolved_at"] = now
        owner.approvals_by_id[normalized_id] = existing

        append_event(
            session_id=str(existing.get("session_id") or ""),
            trace_id=str(existing.get("trace_id") or ""),
            request_id=existing.get("request_ref"),
            event_type="approval.decided",
            created_at=now,
            body={
                "approval_id": normalized_id,
                "proposal_digest": str(existing.get("proposal_digest") or ""),
                "decision_digest": str(existing.get("admission_decision_digest") or ""),
                "status": target_status,
                "resolution": deepcopy(resolution),
            },
        )

        rebuild_pending_approvals(str(existing.get("session_id") or ""))
        return {"status": "resolved", "approval": deepcopy(owner.approvals_by_id[normalized_id])}


__all__ = [
    "APPROVAL_STATUSES",
    "create_approval_request",
    "decide_approval",
    "get_approval",
    "list_approvals",
    "rebuild_pending_approvals",
]
