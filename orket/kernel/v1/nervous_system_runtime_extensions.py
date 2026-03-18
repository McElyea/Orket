from __future__ import annotations

from typing import Any

from .nervous_system_approvals import (
    decide_approval,
    get_approval,
    list_approvals,
    rebuild_pending_approvals,
)
from .nervous_system_policy import require_nervous_system_enabled
from .nervous_system_runtime import _admit_proposal_internal
from .nervous_system_runtime_state import _ADMISSIONS_BY_PROPOSAL, get_str, list_events_for_session
from .nervous_system_tokens import (
    consume_credential_token,
    invalidate_tokens_for_proposal,
    issue_credential_token,
)
from .nervous_system_runtime_state import append_event


def list_approvals_v1(
    *, status: str | None, session_id: str | None, request_id: str | None, limit: int
) -> list[dict[str, Any]]:
    return list_approvals(status=status, session_id=session_id, request_id=request_id, limit=limit)


def get_approval_v1(approval_id: str) -> dict[str, Any] | None:
    return get_approval(approval_id)


def _readmit_edited_proposal(
    session_id: str, trace_id: str, request_id: str | None, edited_proposal: dict[str, Any]
) -> dict[str, Any]:
    return _admit_proposal_internal(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        proposal={"proposal_type": "action.tool_call", "payload": dict(edited_proposal)},
    )


def decide_approval_v1(
    *,
    approval_id: str,
    decision: str,
    edited_proposal: dict[str, Any] | None,
    notes: str | None,
) -> dict[str, Any]:
    result = decide_approval(
        approval_id=approval_id,
        decision=decision,
        edited_proposal=edited_proposal,
        notes=notes,
        readmit_edited_proposal=_readmit_edited_proposal,
    )
    approval = result.get("approval") or {}
    status = str(approval.get("status") or "")
    if status in {"DENIED", "EXPIRED", "APPROVED_WITH_EDITS"}:
        invalidate_tokens_for_proposal(
            session_id=str(approval.get("session_id") or ""),
            proposal_digest=str(approval.get("proposal_digest") or ""),
            reason=f"approval_{status.lower()}",
        )
    return result


def rebuild_pending_approvals_v1(session_id: str) -> list[dict[str, Any]]:
    return rebuild_pending_approvals(session_id)


def list_ledger_events_v1(
    *,
    session_id: str,
    trace_id: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    normalized_trace_id = str(trace_id or "").strip()
    normalized_event_type = str(event_type or "").strip()
    rows: list[dict[str, Any]] = []
    for event in list_events_for_session(session_id):
        if normalized_trace_id and str(event.get("trace_id") or "") != normalized_trace_id:
            continue
        if normalized_event_type and str(event.get("event_type") or "") != normalized_event_type:
            continue
        rows.append(dict(event))
    rows.sort(key=lambda row: (int(row.get("id") or 0), str(row.get("event_digest") or "")))
    return rows[: max(1, int(limit))]


def replay_action_lifecycle_v1(*, session_id: str, trace_id: str) -> dict[str, Any]:
    events = list_ledger_events_v1(session_id=session_id, trace_id=trace_id, limit=1000)
    if not events:
        raise ValueError(f"No ledger events found for session_id='{session_id}' trace_id='{trace_id}'.")

    event_digests_by_type: dict[str, list[str]] = {}
    request_ids: set[str] = set()
    for event in events:
        event_type = str(event.get("event_type") or "")
        event_digests_by_type.setdefault(event_type, []).append(str(event.get("event_digest") or ""))
        request_id = str(event.get("request_id") or "").strip()
        if request_id:
            request_ids.add(request_id)

    admission_event = _last_event_of_type(events, "admission.decided")
    approval_requested_event = _last_event_of_type(events, "approval.requested")
    approval_decided_event = _last_event_of_type(events, "approval.decided")
    commit_event = _last_event_of_type(events, "commit.recorded")
    token_issue_events = _events_of_type(events, "credential.token_issued")
    token_use_events = _events_of_type(events, "credential.token_used")
    execution_event = _last_event_of_type(events, "action.executed")
    validation_event = _last_event_of_type(events, "action.result_validated")

    admission_body = _event_body(admission_event)
    approval_requested_body = _event_body(approval_requested_event)
    approval_decided_body = _event_body(approval_decided_event)
    commit_body = _event_body(commit_event)
    validation_body = _event_body(validation_event)

    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_ids": sorted(request_ids),
        "event_count": len(events),
        "event_types": [str(event.get("event_type") or "") for event in events],
        "event_digests_by_type": event_digests_by_type,
        "decision_summary": {
            "admission_decision": str(admission_body.get("decision") or ""),
            "reason_codes": list(admission_body.get("reason_codes") or []),
            "approval_id": str(approval_requested_body.get("approval_id") or ""),
            "approval_status": str(approval_decided_body.get("status") or ""),
            "commit_status": str(commit_body.get("status") or ""),
        },
        "token_usage": {
            "issued_count": len(token_issue_events),
            "used_count": len(token_use_events),
            "token_id_hashes": sorted(
                {
                    str(_event_body(event).get("token_id_hash") or "")
                    for event in token_issue_events + token_use_events
                    if str(_event_body(event).get("token_id_hash") or "")
                }
            ),
        },
        "execution_summary": {
            "executed": execution_event is not None,
            "validated": validation_event is not None,
            "execution_result_digest": str(_event_body(execution_event).get("execution_result_digest") or ""),
            "sanitization_digest": str(validation_body.get("sanitization_digest") or ""),
        },
        "events": [
            {
                "id": int(event.get("id") or 0),
                "event_type": str(event.get("event_type") or ""),
                "event_digest": str(event.get("event_digest") or ""),
                "created_at": str(event.get("created_at") or ""),
                "request_id": str(event.get("request_id") or ""),
                "prev_event_digest": str(event.get("prev_event_digest") or ""),
                "body": _event_body(event),
            }
            for event in events
        ],
    }


def audit_action_lifecycle_v1(*, session_id: str, trace_id: str) -> dict[str, Any]:
    lifecycle = replay_action_lifecycle_v1(session_id=session_id, trace_id=trace_id)
    decision_summary = dict(lifecycle.get("decision_summary") or {})
    event_digests_by_type = dict(lifecycle.get("event_digests_by_type") or {})
    approval_id = str(decision_summary.get("approval_id") or "")
    approval_status = str(decision_summary.get("approval_status") or "")
    commit_status = str(decision_summary.get("commit_status") or "")
    admission_decision = str(decision_summary.get("admission_decision") or "")
    pending_after_rebuild = rebuild_pending_approvals(session_id)
    pending_approval_ids = sorted(
        str(row.get("approval_id") or "") for row in pending_after_rebuild if str(row.get("approval_id") or "")
    )

    checks = [
        {
            "check": "projection_present",
            "ok": bool(event_digests_by_type.get("projection.issued")),
        },
        {
            "check": "admission_present",
            "ok": bool(event_digests_by_type.get("admission.decided")),
        },
        {
            "check": "commit_present",
            "ok": bool(event_digests_by_type.get("commit.recorded")),
        },
        {
            "check": "approval_path_complete",
            "ok": _approval_path_complete(
                admission_decision=admission_decision,
                event_digests_by_type=event_digests_by_type,
            ),
        },
        {
            "check": "execution_path_consistent",
            "ok": _execution_path_consistent(
                commit_status=commit_status,
                event_digests_by_type=event_digests_by_type,
            ),
        },
        {
            "check": "approval_queue_rebuild_consistent",
            "ok": _approval_queue_rebuild_consistent(
                approval_id=approval_id,
                approval_status=approval_status,
                pending_approval_ids=pending_approval_ids,
            ),
        },
    ]

    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "ok": all(bool(row.get("ok")) for row in checks),
        "checks": checks,
        "pending_approval_ids_after_rebuild": pending_approval_ids,
        "lifecycle": lifecycle,
    }


def issue_credential_token_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    proposal_digest = get_str(request, "proposal_digest", required=True)
    decision_digest = get_str(request, "admission_decision_digest", required=True)
    tool_name = get_str(request, "tool_name", required=True)
    admission = _ADMISSIONS_BY_PROPOSAL.get((session_id, proposal_digest))
    if not admission or str(admission.get("decision_digest") or "") != decision_digest:
        raise ValueError("invalid proposal_digest/admission_decision_digest binding")

    admission_decision = str((admission.get("admission_decision") or {}).get("decision") or "")
    if admission_decision == "NEEDS_APPROVAL":
        approval_id = get_str(request, "approval_id", required=False)
        approval = get_approval(approval_id) if approval_id else None
        if not approval or str(approval.get("status") or "") != "APPROVED":
            raise ValueError("approved approval_id is required before issuing a credential token")

    scope_json = request.get("scope_json")
    if not isinstance(scope_json, dict):
        raise ValueError("scope_json must be an object")
    tool_profile_definition = request.get("tool_profile_definition")
    if not isinstance(tool_profile_definition, dict):
        raise ValueError("tool_profile_definition must be an object")
    return issue_credential_token(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        proposal_digest=proposal_digest,
        admission_decision_digest=decision_digest,
        tool_name=tool_name,
        scope_json=scope_json,
        tool_profile_definition=tool_profile_definition,
        executor_instance_id=get_str(request, "executor_instance_id", required=False),
        expires_in_seconds=int(request.get("expires_in_seconds") or 900),
        append_event=append_event,
    )


def consume_credential_token_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    raw_token = get_str(request, "token", required=True)
    proposal_digest = get_str(request, "proposal_digest", required=True)
    tool_name = get_str(request, "tool_name", required=True)
    scope_json = request.get("scope_json")
    if not isinstance(scope_json, dict):
        raise ValueError("scope_json must be an object")
    return consume_credential_token(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        raw_token=raw_token,
        proposal_digest=proposal_digest,
        tool_name=tool_name,
        scope_json=scope_json,
        executor_instance_id=get_str(request, "executor_instance_id", required=False),
        expected_tool_profile_digest=get_str(request, "tool_profile_digest", required=False),
        append_event=append_event,
    )


def get_session_ledger_events_v1(session_id: str) -> list[dict[str, Any]]:
    return list_events_for_session(session_id)


def _events_of_type(events: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [event for event in events if str(event.get("event_type") or "") == event_type]


def _last_event_of_type(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    matched = _events_of_type(events, event_type)
    if not matched:
        return None
    return dict(matched[-1])


def _event_body(event: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    body = event.get("body")
    return dict(body) if isinstance(body, dict) else {}


def _approval_path_complete(*, admission_decision: str, event_digests_by_type: dict[str, list[str]]) -> bool:
    if admission_decision != "NEEDS_APPROVAL":
        return True
    return bool(event_digests_by_type.get("approval.requested")) and bool(event_digests_by_type.get("approval.decided"))


def _execution_path_consistent(*, commit_status: str, event_digests_by_type: dict[str, list[str]]) -> bool:
    executed = bool(event_digests_by_type.get("action.executed"))
    validated = bool(event_digests_by_type.get("action.result_validated"))
    if commit_status == "COMMITTED":
        return executed and validated
    return not executed and not validated


def _approval_queue_rebuild_consistent(
    *, approval_id: str, approval_status: str, pending_approval_ids: list[str]
) -> bool:
    if not approval_id:
        return True
    if approval_status == "PENDING":
        return approval_id in pending_approval_ids
    return approval_id not in pending_approval_ids


__all__ = [
    "audit_action_lifecycle_v1",
    "consume_credential_token_v1",
    "decide_approval_v1",
    "get_approval_v1",
    "list_ledger_events_v1",
    "get_session_ledger_events_v1",
    "issue_credential_token_v1",
    "list_approvals_v1",
    "replay_action_lifecycle_v1",
    "rebuild_pending_approvals_v1",
]
