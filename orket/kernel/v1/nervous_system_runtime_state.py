from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, overload

from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_runtime_owner import current_kernel_runtime

from .canonical import digest_of
from .nervous_system_contract import GENESIS_STATE_DIGEST

CONTRACT_VERSION = "kernel_api/v1"


@overload
def get_str(payload: dict[str, Any], key: str, *, required: Literal[True]) -> str: ...


@overload
def get_str(payload: dict[str, Any], key: str, *, required: Literal[False] = False) -> str | None: ...


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
    owner = current_kernel_runtime()
    with owner.lock:
        return owner.session_canonical_state.get(session_id, GENESIS_STATE_DIGEST)


def set_current_canonical_state_digest(session_id: str, canonical_state_digest: str) -> None:
    owner = current_kernel_runtime()
    with owner.lock:
        owner.session_canonical_state[session_id] = canonical_state_digest


def append_event(
    *,
    session_id: str,
    trace_id: str,
    event_type: str,
    body: dict[str, Any],
    request_id: str | None = None,
    created_at: str,
) -> dict[str, Any]:

    owner = current_kernel_runtime()
    body = capture_kernel_request(body)
    with owner.lock:
        previous = owner.session_event_heads.get(session_id)
        event = {
            "id": owner.next_ledger_id,
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
        if event_digest in owner.events_by_digest:
            raise RuntimeError("event_digest collision detected")
        event["event_digest"] = event_digest

        owner.next_ledger_id += 1
        owner.ledger_by_session.setdefault(session_id, []).append(event)
        owner.events_by_digest[event_digest] = event
        owner.session_event_heads[session_id] = event_digest
        return deepcopy(event)


def list_events_for_session(session_id: str) -> list[dict[str, Any]]:
    owner = current_kernel_runtime()
    with owner.lock:
        return deepcopy(owner.ledger_by_session.get(session_id, []))


def has_admission_event(
    *,
    session_id: str,
    proposal_digest: str,
    admission_decision_digest: str,
) -> bool:
    owner = current_kernel_runtime()
    for event in owner.ledger_by_session.get(session_id, []):
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
    owner = current_kernel_runtime()
    with owner.lock:
        return sorted(owner.ledger_by_session.keys())


__all__ = [
    "CONTRACT_VERSION",
    "append_event",
    "get_current_canonical_state_digest",
    "get_str",
    "has_admission_event",
    "list_events_for_session",
    "list_session_ids",
    "normalized_optional_str",
    "set_current_canonical_state_digest",
]
