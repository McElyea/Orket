from __future__ import annotations

from typing import Any

from .canonical import digest_of
from .nervous_system_approvals import (
    create_approval_request,
    get_approval,
)
from .nervous_system_contract import (
    ADMISSION_DECISIONS_V1,
    COMMIT_STATUSES_V1,
    NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
    ordered_reason_codes_v1,
)
from .nervous_system_leaks import find_leak_hits, sanitize_text
from .nervous_system_policy import (
    allow_pre_resolved_policy_flags,
    is_exfil_payload,
    require_nervous_system_enabled,
    use_tool_profile_resolver,
)
from .nervous_system_resolver import resolve_tool_policy_flags
from .nervous_system_runtime_state import (
    CONTRACT_VERSION,
    _ADMISSIONS_BY_PROPOSAL,
    _COMMIT_RESULTS_BY_KEY,
    _RUNTIME_LOCK,
    append_event,
    get_current_canonical_state_digest,
    get_str,
    has_admission_event,
    normalized_optional_str,
    set_current_canonical_state_digest,
    utc_iso_now,
)
from .nervous_system_tokens import (
    invalidate_tokens_for_session,
)

_POLICY_FLAG_KEYS = (
    "policy_forbidden",
    "scope_violation",
    "unknown_tool_profile",
    "approval_required_destructive",
    "approval_required_exfil",
    "approval_required_credentialed",
)


def projection_pack_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    purpose = get_str(request, "purpose", required=True)
    if purpose != NERVOUS_SYSTEM_PURPOSE_ACTION_PATH:
        raise ValueError(f"purpose must be {NERVOUS_SYSTEM_PURPOSE_ACTION_PATH}")

    canonical_state_digest = get_str(request, "canonical_state_digest", required=False)
    if canonical_state_digest is None:
        canonical_state_digest = get_current_canonical_state_digest(session_id)

    policy_context = request.get("policy_context")
    if policy_context is None:
        policy_context = {}
    if not isinstance(policy_context, dict):
        raise ValueError("policy_context must be an object")

    tool_context_summary = request.get("tool_context_summary")
    if tool_context_summary is None:
        tool_context_summary = {}
    if not isinstance(tool_context_summary, dict):
        raise ValueError("tool_context_summary must be an object")

    contract_digest = digest_of(
        {
            "contract_version": CONTRACT_VERSION,
            "surface": "nervous_system_action_path_v1",
            "purpose": NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
        }
    )
    policy_digest = digest_of(policy_context)
    projection_pack = {
        "pack_id": f"pp-{digest_of({'session_id': session_id, 'trace_id': trace_id, 'request_id': request_id})[:16]}",
        "created_at": utc_iso_now(),
        "purpose": NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
        "canonical": {
            "canonical_state_digest": canonical_state_digest,
            "contract_digest": contract_digest,
        },
        "policy_summary": {
            "policy_digest": policy_digest,
        },
        "tool_context_summary": tool_context_summary,
    }
    projection_pack_digest = digest_of(projection_pack)
    event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="projection.issued",
        body={
            "projection_pack_digest": projection_pack_digest,
            "policy_digest": policy_digest,
            "contract_digest": contract_digest,
        },
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "projection_pack": projection_pack,
        "projection_pack_digest": projection_pack_digest,
        "policy_digest": policy_digest,
        "contract_digest": contract_digest,
        "canonical_state_digest": canonical_state_digest,
        "event_digest": event["event_digest"],
    }


def _admission_from_proposal(proposal: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    proposal_type = proposal.get("proposal_type")
    if proposal_type != "action.tool_call":
        return "REJECT", ["SCHEMA_INVALID"], []

    payload = proposal.get("payload")
    if not isinstance(payload, dict):
        return "REJECT", ["SCHEMA_INVALID"], []

    effective_payload = dict(payload)
    if use_tool_profile_resolver():
        resolved_flags = resolve_tool_policy_flags(payload)
        for key in _POLICY_FLAG_KEYS:
            effective_payload[key] = bool(payload.get(key)) or bool(resolved_flags.get(key))
    elif not allow_pre_resolved_policy_flags():
        effective_payload["unknown_tool_profile"] = True
        effective_payload["policy_forbidden"] = False
        effective_payload["scope_violation"] = False
        effective_payload["approval_required_destructive"] = False
        effective_payload["approval_required_exfil"] = False
        effective_payload["approval_required_credentialed"] = False

    if bool(effective_payload.get("policy_forbidden")):
        return "REJECT", ["POLICY_FORBIDDEN"], []

    leak_hits = find_leak_hits(payload.get("outbound_payload", payload))
    if bool(effective_payload.get("leak_detected")) or (leak_hits and is_exfil_payload(effective_payload)):
        return "REJECT", ["LEAK_DETECTED"], leak_hits

    if bool(effective_payload.get("scope_violation")):
        return "REJECT", ["SCOPE_VIOLATION"], []

    if bool(effective_payload.get("unknown_tool_profile")):
        return "NEEDS_APPROVAL", ["UNKNOWN_TOOL_PROFILE"], []

    approval_reasons: list[str] = []
    if bool(effective_payload.get("approval_required_destructive")):
        approval_reasons.append("APPROVAL_REQUIRED_DESTRUCTIVE")
    if bool(effective_payload.get("approval_required_exfil")) or is_exfil_payload(effective_payload):
        approval_reasons.append("APPROVAL_REQUIRED_EXFIL")
    if bool(effective_payload.get("approval_required_credentialed")):
        approval_reasons.append("APPROVAL_REQUIRED_CREDENTIALED")
    if approval_reasons:
        return "NEEDS_APPROVAL", ordered_reason_codes_v1(approval_reasons), []

    return "ACCEPT_TO_UNIFY", [], []


def _admit_proposal_internal(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    proposal_digest = digest_of(proposal)
    decision, reason_codes, leak_hits = _admission_from_proposal(proposal)
    if decision not in ADMISSION_DECISIONS_V1:
        raise ValueError("invalid admission decision")

    admission = {
        "decision": decision,
        "reason_codes": ordered_reason_codes_v1(reason_codes),
    }
    decision_digest = digest_of(admission)

    with _RUNTIME_LOCK:
        _ADMISSIONS_BY_PROPOSAL[(session_id, proposal_digest)] = {
            "session_id": session_id,
            "trace_id": trace_id,
            "request_id": request_id,
            "proposal_digest": proposal_digest,
            "admission_decision": admission,
            "decision_digest": decision_digest,
        }

    append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="proposal.received",
        body={"proposal_digest": proposal_digest},
    )
    admission_event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="admission.decided",
        body={
            "proposal_digest": proposal_digest,
            "decision_digest": decision_digest,
            "decision": decision,
            "reason_codes": admission["reason_codes"],
        },
    )

    if leak_hits:
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="incident.detected",
            body={
                "stage": "admission",
                "proposal_digest": proposal_digest,
                "reason_codes": ["LEAK_DETECTED"],
                "detector_hits": list(leak_hits),
            },
        )

    response = {
        "contract_version": CONTRACT_VERSION,
        "proposal_digest": proposal_digest,
        "admission_decision": admission,
        "decision_digest": decision_digest,
        "event_digest": admission_event["event_digest"],
    }

    if decision == "NEEDS_APPROVAL":
        approval = create_approval_request(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            proposal_digest=proposal_digest,
            decision_digest=decision_digest,
            reason_codes=admission["reason_codes"],
        )
        response["approval_id"] = approval["approval_id"]

    return response


def admit_proposal_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    proposal = request.get("proposal")
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")

    return _admit_proposal_internal(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        proposal=proposal,
    )


def commit_proposal_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    proposal_digest = get_str(request, "proposal_digest", required=True)
    admission_decision_digest = get_str(request, "admission_decision_digest", required=True)
    approval_id = normalized_optional_str(request.get("approval_id"))
    execution_result_digest = normalized_optional_str(request.get("execution_result_digest"))
    commit_key = (proposal_digest, admission_decision_digest, approval_id, execution_result_digest)

    with _RUNTIME_LOCK:
        existing = _COMMIT_RESULTS_BY_KEY.get(commit_key)
        if existing is not None:
            return dict(existing)

    status = "COMMITTED"
    result_reason_codes: list[str] = []
    reported_sanitization_digest = normalized_optional_str(request.get("sanitization_digest"))
    # Top-level entry point: return explicit ERROR only for internal failures.
    try:
        admission = _ADMISSIONS_BY_PROPOSAL.get((session_id, proposal_digest))
        if (
            not admission
            or admission.get("decision_digest") != admission_decision_digest
            or not has_admission_event(
                session_id=session_id,
                proposal_digest=proposal_digest,
                admission_decision_digest=admission_decision_digest,
            )
        ):
            status = "REJECTED_PRECONDITION"
        else:
            decision = str(admission["admission_decision"]["decision"])
            if decision == "REJECT":
                status = "REJECTED_POLICY"
            elif decision == "NEEDS_APPROVAL":
                approval = get_approval(approval_id) if approval_id else None
                if not approval or str(approval.get("status") or "") != "APPROVED":
                    status = "REJECTED_APPROVAL_MISSING"
            if status == "COMMITTED" and bool(request.get("revalidate_policy_forbidden")):
                status = "REJECTED_POLICY"

            execution_result_payload = request.get("execution_result_payload")
            if status == "COMMITTED" and execution_result_payload is not None:
                leak_hits = find_leak_hits(execution_result_payload)
                if leak_hits:
                    result_reason_codes.append("RESULT_LEAK_DETECTED")
                    append_event(
                        session_id=session_id,
                        trace_id=trace_id,
                        request_id=request_id,
                        event_type="incident.detected",
                        body={
                            "stage": "action_result",
                            "proposal_digest": proposal_digest,
                            "reason_codes": ["RESULT_LEAK_DETECTED"],
                            "detector_hits": leak_hits,
                        },
                    )
                    if bool(request.get("block_result_leaks")):
                        status = "REJECTED_POLICY"
                    elif not reported_sanitization_digest and isinstance(execution_result_payload, str):
                        reported_sanitization_digest = digest_of(
                            {"sanitized": sanitize_text(execution_result_payload)}
                        )

            if status == "COMMITTED" and request.get("execution_result_schema_valid") is False:
                result_reason_codes.append("RESULT_SCHEMA_INVALID")
                status = "REJECTED_POLICY"

            execution_error_reason_code = normalized_optional_str(request.get("execution_error_reason_code")).upper()
            if status == "COMMITTED" and execution_error_reason_code in {"TOKEN_INVALID", "TOKEN_EXPIRED", "TOKEN_REPLAY"}:
                result_reason_codes.append(execution_error_reason_code)
                status = "REJECTED_POLICY"
    except Exception:
        status = "ERROR"

    if status not in COMMIT_STATUSES_V1:
        status = "ERROR"

    executed = status == "COMMITTED" and bool(execution_result_digest)
    if executed:
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="action.executed",
            body={
                "proposal_digest": proposal_digest,
                "execution_result_digest": execution_result_digest,
            },
        )

    if executed:
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="action.result_validated",
            body={
                "proposal_digest": proposal_digest,
                "execution_result_digest": execution_result_digest or None,
                "status": "PASS" if status == "COMMITTED" else "FAIL",
                "reason_codes": ordered_reason_codes_v1(result_reason_codes),
                "sanitization_digest": reported_sanitization_digest or None,
            },
        )

    canonical_state_digest_after = get_str(request, "canonical_state_digest_after", required=False)
    if canonical_state_digest_after and status == "COMMITTED":
        set_current_canonical_state_digest(session_id, canonical_state_digest_after)

    body = {
        "proposal_digest": proposal_digest,
        "admission_decision_digest": admission_decision_digest,
        "approval_id": approval_id or None,
        "execution_result_digest": execution_result_digest or None,
        "sanitization_digest": reported_sanitization_digest or None,
        "status": status,
    }
    commit_event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="commit.recorded",
        body=body,
    )
    response = {
        "contract_version": CONTRACT_VERSION,
        "status": status,
        "commit_event_digest": commit_event["event_digest"],
        "canonical_state_digest": get_current_canonical_state_digest(session_id),
    }
    if reported_sanitization_digest:
        response["sanitization_digest"] = reported_sanitization_digest

    with _RUNTIME_LOCK:
        _COMMIT_RESULTS_BY_KEY[commit_key] = dict(response)
    return response


def end_session_v1(request: dict[str, Any]) -> dict[str, Any]:
    require_nervous_system_enabled()
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    reason = normalized_optional_str(request.get("reason"))

    invalidated = invalidate_tokens_for_session(session_id=session_id, reason="session_ended")
    event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="session.ended",
        body={"reason": reason or None, "invalidated_token_count": invalidated},
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "session_id": session_id,
        "event_digest": event["event_digest"],
        "canonical_state_digest": get_current_canonical_state_digest(session_id),
        "status": "ENDED",
    }


__all__ = [
    "_admit_proposal_internal",
    "admit_proposal_v1",
    "commit_proposal_v1",
    "end_session_v1",
    "projection_pack_v1",
]
