"""Application-owned in-memory credential effects over explicit trusted inputs."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from orket.core.contracts.kernel_credentials import (
    CredentialBinding,
    CredentialIssueInputs,
    CredentialObservation,
    CredentialRecord,
    credential_hash,
    credential_id_hash,
    credential_is_expired,
    credential_observation_time,
    credential_refusal,
)

from .nervous_system_contract import canonical_scope_digest, tool_profile_digest
from .nervous_system_runtime_state import _RUNTIME_LOCK, _TOKENS_BY_HASH

AppendEventFn = Callable[..., dict[str, Any]]


def issue_credential_token(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    proposal_digest: str,
    admission_decision_digest: str,
    tool_name: str,
    scope_json: dict[str, Any],
    tool_profile_definition: dict[str, Any],
    append_event: AppendEventFn,
    inputs: CredentialIssueInputs,
    executor_instance_id: str | None = None,
    expires_in_seconds: int = 900,
) -> dict[str, Any]:
    if not isinstance(inputs, CredentialIssueInputs):
        raise TypeError("E_CREDENTIAL_ISSUE_INPUTS_REQUIRED")
    scope_json, tool_profile_definition = deepcopy(scope_json), deepcopy(tool_profile_definition)
    created_at = inputs.observed_at.isoformat()
    expires_at = (inputs.observed_at + timedelta(seconds=max(1, int(expires_in_seconds)))).isoformat()
    token_hash = credential_hash(inputs.raw_token, inputs)
    token_id_h = credential_id_hash(inputs.token_id)
    scope_digest, profile_digest = canonical_scope_digest(scope_json), tool_profile_digest(tool_profile_definition)
    with _RUNTIME_LOCK:
        if token_hash in _TOKENS_BY_HASH or any(
            record.get("token_id_hash") == token_id_h for record in _TOKENS_BY_HASH.values()
        ):
            raise ValueError("E_CREDENTIAL_IDENTITY_REUSE")
        _TOKENS_BY_HASH[token_hash] = {
            "token_id_hash": token_id_h,
            "session_id": session_id,
            "trace_id": trace_id,
            "request_id": request_id,
            "proposal_digest": proposal_digest,
            "admission_decision_digest": admission_decision_digest,
            "tool_name": tool_name,
            "scope_json": scope_json,
            "scope_digest": scope_digest,
            "tool_profile_digest": profile_digest,
            "executor_instance_id": executor_instance_id,
            "created_at": created_at,
            "expires_at": expires_at,
            "used_at": None,
            "invalidated_at": None,
            "invalidation_reason": None,
        }
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="credential.token_issued",
            created_at=created_at,
            body={
                "token_id_hash": token_id_h,
                "token_hash": token_hash,
                "proposal_digest": proposal_digest,
                "admission_decision_digest": admission_decision_digest,
                "tool_name": tool_name,
                "scope_digest": scope_digest,
                "tool_profile_digest": profile_digest,
                "executor_instance_id": executor_instance_id,
                "expires_at": expires_at,
            },
        )
    return {
        "token": inputs.raw_token,
        "token_id_hash": token_id_h,
        "token_hash": token_hash,
        "scope_digest": scope_digest,
        "tool_profile_digest": profile_digest,
        "expires_at": expires_at,
    }


def consume_credential_token(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    raw_token: str,
    proposal_digest: str,
    tool_name: str,
    scope_json: dict[str, Any],
    append_event: AppendEventFn,
    inputs: CredentialObservation,
    executor_instance_id: str | None = None,
    expected_tool_profile_digest: str | None = None,
) -> dict[str, Any]:
    if not isinstance(inputs, CredentialObservation):
        raise TypeError("E_CREDENTIAL_OBSERVATION_REQUIRED")
    normalized_raw = str(raw_token or "").strip()
    if not normalized_raw:
        return {"ok": False, "reason_code": "TOKEN_INVALID"}
    token_hash = credential_hash(normalized_raw, inputs)
    scope_digest = canonical_scope_digest(deepcopy(scope_json))
    binding = CredentialBinding(
        session_id,
        proposal_digest,
        tool_name,
        scope_digest,
        str(executor_instance_id or "").strip(),
        str(expected_tool_profile_digest or ""),
    )
    observed_at = inputs.observed_at.isoformat()
    with _RUNTIME_LOCK:
        record = _TOKENS_BY_HASH.get(token_hash)
        if not record:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}
        reason = credential_refusal(_record_view(record), binding, inputs)
        if reason:
            if reason == "TOKEN_EXPIRED" and credential_is_expired(
                str(record.get("expires_at") or ""), inputs.observed_at
            ):
                record["invalidated_at"], record["invalidation_reason"] = observed_at, "expired"
            return {"ok": False, "reason_code": reason}
        record["used_at"], record["invalidated_at"], record["invalidation_reason"] = observed_at, observed_at, "used"
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="credential.token_used",
            created_at=observed_at,
            body={
                "token_id_hash": str(record.get("token_id_hash") or ""),
                "token_hash": token_hash,
                "proposal_digest": proposal_digest,
                "tool_name": tool_name,
                "scope_digest": scope_digest,
                "executor_instance_id": executor_instance_id,
                "used_at": observed_at,
            },
        )
        return {
            "ok": True,
            "reason_code": "",
            "token_id_hash": str(record.get("token_id_hash") or ""),
            "token_hash": token_hash,
        }


def _record_view(record: dict[str, Any]) -> CredentialRecord:
    return CredentialRecord(
        session_id=str(record.get("session_id") or ""),
        proposal_digest=str(record.get("proposal_digest") or ""),
        tool_name=str(record.get("tool_name") or ""),
        scope_digest=str(record.get("scope_digest") or ""),
        executor_instance_id=str(record.get("executor_instance_id") or "").strip(),
        tool_profile_digest=str(record.get("tool_profile_digest") or ""),
        expires_at=str(record.get("expires_at") or ""),
        used=bool(record.get("used_at")),
        invalidated=bool(record.get("invalidated_at")),
        invalidation_reason=str(record.get("invalidation_reason") or "").strip().lower(),
    )


def invalidate_tokens_for_session(*, session_id: str, reason: str, observed_at: datetime) -> int:
    return _invalidate(session_id=session_id, proposal_digest=None, reason=reason, observed_at=observed_at)


def invalidate_tokens_for_proposal(*, session_id: str, proposal_digest: str, reason: str, observed_at: datetime) -> int:
    return _invalidate(session_id=session_id, proposal_digest=proposal_digest, reason=reason, observed_at=observed_at)


def _invalidate(*, session_id, proposal_digest, reason, observed_at) -> int:
    timestamp = credential_observation_time(observed_at).isoformat()
    invalidated = 0
    with _RUNTIME_LOCK:
        for record in _TOKENS_BY_HASH.values():
            if str(record.get("session_id") or "") != session_id or record.get("invalidated_at"):
                continue
            if proposal_digest is not None and str(record.get("proposal_digest") or "") != proposal_digest:
                continue
            record["invalidated_at"], record["invalidation_reason"] = timestamp, reason
            invalidated += 1
    return invalidated


__all__ = [
    "consume_credential_token",
    "invalidate_tokens_for_proposal",
    "invalidate_tokens_for_session",
    "issue_credential_token",
]
