from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Any

from .canonical import digest_of
from .nervous_system_contract import GENESIS_STATE_DIGEST

CONTRACT_VERSION = "kernel_api/v1"

_RUNTIME_LOCK = RLock()

_NEXT_LEDGER_ID = 1
_SESSION_EVENT_HEADS: dict[str, str] = {}
_SESSION_CANONICAL_STATE: dict[str, str] = {}
_LEDGER_BY_SESSION: dict[str, list[dict[str, Any]]] = {}
_EVENTS_BY_DIGEST: dict[str, dict[str, Any]] = {}

_ADMISSIONS_BY_PROPOSAL: dict[tuple[str, str], dict[str, Any]] = {}
_COMMIT_RESULTS_BY_KEY: dict[tuple[str, str, str, str], dict[str, Any]] = {}

_APPROVALS_BY_ID: dict[str, dict[str, Any]] = {}
_PENDING_APPROVALS_CACHE: dict[str, list[dict[str, Any]]] = {}

_TOKENS_BY_HASH: dict[str, dict[str, Any]] = {}


def utc_iso_now() -> str:
    return datetime.now(UTC).isoformat()


def get_str(payload: dict[str, Any], key: str, *, required: bool = False) -> str | None:
    value = payload.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def normalized_optional_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def get_current_canonical_state_digest(session_id: str) -> str:
    return _SESSION_CANONICAL_STATE.get(session_id, GENESIS_STATE_DIGEST)


def set_current_canonical_state_digest(session_id: str, canonical_state_digest: str) -> None:
    _SESSION_CANONICAL_STATE[session_id] = canonical_state_digest


def append_event(
    *,
    session_id: str,
    trace_id: str,
    event_type: str,
    body: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    global _NEXT_LEDGER_ID

    created_at = utc_iso_now()
    with _RUNTIME_LOCK:
        previous = _SESSION_EVENT_HEADS.get(session_id)
        event = {
            "id": _NEXT_LEDGER_ID,
            "contract_version": CONTRACT_VERSION,
            "session_id": session_id,
            "trace_id": trace_id,
            "request_id": request_id or None,
            "event_type": event_type,
            "created_at": created_at,
            "prev_event_digest": previous,
            "body": body,
        }
        event_digest = digest_of(event)
        if event_digest in _EVENTS_BY_DIGEST:
            raise RuntimeError("event_digest collision detected")
        event["event_digest"] = event_digest

        _NEXT_LEDGER_ID += 1
        _LEDGER_BY_SESSION.setdefault(session_id, []).append(event)
        _EVENTS_BY_DIGEST[event_digest] = event
        _SESSION_EVENT_HEADS[session_id] = event_digest
        return event


def list_events_for_session(session_id: str) -> list[dict[str, Any]]:
    events = _LEDGER_BY_SESSION.get(session_id, [])
    return [dict(event) for event in events]


def has_admission_event(
    *,
    session_id: str,
    proposal_digest: str,
    admission_decision_digest: str,
) -> bool:
    for event in _LEDGER_BY_SESSION.get(session_id, []):
        if event.get("event_type") != "admission.decided":
            continue
        body = event.get("body")
        if not isinstance(body, dict):
            continue
        if (
            str(body.get("proposal_digest") or "") == proposal_digest
            and str(body.get("decision_digest") or "") == admission_decision_digest
        ):
            return True
    return False


def list_session_ids() -> list[str]:
    return sorted(_LEDGER_BY_SESSION.keys())


def reset_runtime_state_for_tests() -> None:
    global _NEXT_LEDGER_ID
    with _RUNTIME_LOCK:
        _NEXT_LEDGER_ID = 1
        _SESSION_EVENT_HEADS.clear()
        _SESSION_CANONICAL_STATE.clear()
        _LEDGER_BY_SESSION.clear()
        _EVENTS_BY_DIGEST.clear()
        _ADMISSIONS_BY_PROPOSAL.clear()
        _COMMIT_RESULTS_BY_KEY.clear()
        _APPROVALS_BY_ID.clear()
        _PENDING_APPROVALS_CACHE.clear()
        _TOKENS_BY_HASH.clear()


__all__ = [
    "CONTRACT_VERSION",
    "_ADMISSIONS_BY_PROPOSAL",
    "_APPROVALS_BY_ID",
    "_COMMIT_RESULTS_BY_KEY",
    "_LEDGER_BY_SESSION",
    "_PENDING_APPROVALS_CACHE",
    "_RUNTIME_LOCK",
    "_TOKENS_BY_HASH",
    "append_event",
    "get_current_canonical_state_digest",
    "get_str",
    "has_admission_event",
    "list_events_for_session",
    "list_session_ids",
    "normalized_optional_str",
    "reset_runtime_state_for_tests",
    "set_current_canonical_state_digest",
    "utc_iso_now",
]
