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


def list_approvals_v1(*, status: str | None, session_id: str | None, request_id: str | None, limit: int) -> list[dict[str, Any]]:
    return list_approvals(status=status, session_id=session_id, request_id=request_id, limit=limit)


def get_approval_v1(approval_id: str) -> dict[str, Any] | None:
    return get_approval(approval_id)


def _readmit_edited_proposal(session_id: str, trace_id: str, request_id: str | None, edited_proposal: dict[str, Any]) -> dict[str, Any]:
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


__all__ = [
    "consume_credential_token_v1",
    "decide_approval_v1",
    "get_approval_v1",
    "get_session_ledger_events_v1",
    "issue_credential_token_v1",
    "list_approvals_v1",
    "rebuild_pending_approvals_v1",
]
