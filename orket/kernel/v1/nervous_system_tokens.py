from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hmac
import hashlib
import os
import secrets
from typing import Any

from .nervous_system_contract import canonical_scope_digest, tool_profile_digest
from .nervous_system_runtime_state import _RUNTIME_LOCK, _TOKENS_BY_HASH, utc_iso_now


def _hmac_key() -> bytes:
    configured = str(os.environ.get("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY") or "").strip()
    if configured:
        return configured.encode("utf-8")
    return b"orket-nervous-system-dev-hmac-key"


def _token_hash(raw_token: str) -> str:
    return hmac.new(_hmac_key(), raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def _token_id_hash(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def _parse_expires_at(expires_at: str) -> datetime:
    parsed = datetime.fromisoformat(str(expires_at))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_token_expired(record: dict[str, Any]) -> bool:
    try:
        expires_at = _parse_expires_at(str(record.get("expires_at") or ""))
    except (TypeError, ValueError):
        return True
    return datetime.now(UTC) >= expires_at


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
    append_event,
    executor_instance_id: str | None = None,
    expires_in_seconds: int = 900,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    safe_ttl = max(1, int(expires_in_seconds))
    expires_at = (now + timedelta(seconds=safe_ttl)).isoformat()

    raw_token = secrets.token_urlsafe(32)
    token_id = f"tok-{secrets.token_hex(12)}"
    token_hash = _token_hash(raw_token)
    token_id_h = _token_id_hash(token_id)
    scope_digest = canonical_scope_digest(scope_json)
    profile_digest = tool_profile_digest(tool_profile_definition)

    with _RUNTIME_LOCK:
        _TOKENS_BY_HASH[token_hash] = {
            "token_id_hash": token_id_h,
            "session_id": session_id,
            "trace_id": trace_id,
            "request_id": request_id,
            "proposal_digest": proposal_digest,
            "admission_decision_digest": admission_decision_digest,
            "tool_name": tool_name,
            "scope_json": dict(scope_json),
            "scope_digest": scope_digest,
            "tool_profile_digest": profile_digest,
            "executor_instance_id": executor_instance_id,
            "created_at": utc_iso_now(),
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
        "token": raw_token,
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
    append_event,
    executor_instance_id: str | None = None,
    expected_tool_profile_digest: str | None = None,
) -> dict[str, Any]:
    normalized_raw = str(raw_token or "").strip()
    if not normalized_raw:
        return {"ok": False, "reason_code": "TOKEN_INVALID"}

    token_hash = _token_hash(normalized_raw)
    scope_digest = canonical_scope_digest(scope_json)

    with _RUNTIME_LOCK:
        record = _TOKENS_BY_HASH.get(token_hash)
        if not record:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}

        if str(record.get("session_id") or "") != session_id:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}
        if str(record.get("proposal_digest") or "") != proposal_digest:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}
        if str(record.get("tool_name") or "") != tool_name:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}
        if str(record.get("scope_digest") or "") != scope_digest:
            return {"ok": False, "reason_code": "TOKEN_INVALID"}

        bound_executor = str(record.get("executor_instance_id") or "").strip()
        if bound_executor and bound_executor != str(executor_instance_id or "").strip():
            return {"ok": False, "reason_code": "TOKEN_INVALID"}

        if expected_tool_profile_digest and str(record.get("tool_profile_digest") or "") != str(expected_tool_profile_digest):
            return {"ok": False, "reason_code": "TOKEN_INVALID"}

        if _is_token_expired(record):
            record["invalidated_at"] = utc_iso_now()
            record["invalidation_reason"] = "expired"
            _TOKENS_BY_HASH[token_hash] = record
            return {"ok": False, "reason_code": "TOKEN_EXPIRED"}

        if record.get("used_at"):
            return {"ok": False, "reason_code": "TOKEN_REPLAY"}
        if record.get("invalidated_at"):
            invalidation_reason = str(record.get("invalidation_reason") or "").strip().lower()
            if invalidation_reason == "expired":
                return {"ok": False, "reason_code": "TOKEN_EXPIRED"}
            if invalidation_reason == "used":
                return {"ok": False, "reason_code": "TOKEN_REPLAY"}
            return {"ok": False, "reason_code": "TOKEN_INVALID"}

        used_at = utc_iso_now()
        record["used_at"] = used_at
        record["invalidated_at"] = used_at
        record["invalidation_reason"] = "used"
        _TOKENS_BY_HASH[token_hash] = record

    append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="credential.token_used",
        body={
            "token_id_hash": str(record.get("token_id_hash") or ""),
            "token_hash": token_hash,
            "proposal_digest": proposal_digest,
            "tool_name": tool_name,
            "scope_digest": scope_digest,
            "executor_instance_id": executor_instance_id,
            "used_at": used_at,
        },
    )
    return {
        "ok": True,
        "reason_code": "",
        "token_id_hash": str(record.get("token_id_hash") or ""),
        "token_hash": token_hash,
    }


def invalidate_tokens_for_session(*, session_id: str, reason: str) -> int:
    invalidated = 0
    now = utc_iso_now()
    with _RUNTIME_LOCK:
        for token_hash, record in list(_TOKENS_BY_HASH.items()):
            if str(record.get("session_id") or "") != session_id:
                continue
            if record.get("invalidated_at"):
                continue
            record["invalidated_at"] = now
            record["invalidation_reason"] = reason
            _TOKENS_BY_HASH[token_hash] = record
            invalidated += 1
    return invalidated


def invalidate_tokens_for_proposal(*, session_id: str, proposal_digest: str, reason: str) -> int:
    invalidated = 0
    now = utc_iso_now()
    with _RUNTIME_LOCK:
        for token_hash, record in list(_TOKENS_BY_HASH.items()):
            if str(record.get("session_id") or "") != session_id:
                continue
            if str(record.get("proposal_digest") or "") != proposal_digest:
                continue
            if record.get("invalidated_at"):
                continue
            record["invalidated_at"] = now
            record["invalidation_reason"] = reason
            _TOKENS_BY_HASH[token_hash] = record
            invalidated += 1
    return invalidated


__all__ = [
    "consume_credential_token",
    "invalidate_tokens_for_proposal",
    "invalidate_tokens_for_session",
    "issue_credential_token",
]
