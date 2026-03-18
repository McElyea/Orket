from __future__ import annotations


RESULT_ERROR_INVARIANT_CONTRACT_SCHEMA_VERSION = "1.0"

_FAILURE_FORBIDDEN_STATUSES: tuple[str, ...] = ("done", "incomplete", "running")
_FAILURE_FORBIDDEN_STATUS_SET = set(_FAILURE_FORBIDDEN_STATUSES)


def result_error_invariant_contract_snapshot() -> dict[str, object]:
    return {
        "schema_version": RESULT_ERROR_INVARIANT_CONTRACT_SCHEMA_VERSION,
        "failure_forbidden_statuses": list(_FAILURE_FORBIDDEN_STATUSES),
    }


def validate_result_error_invariant_contract(
    payload: dict[str, object] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or result_error_invariant_contract_snapshot())
    statuses = [
        str(token).strip().lower() for token in contract.get("failure_forbidden_statuses", []) if str(token).strip()
    ]
    if not statuses:
        raise ValueError("E_RESULT_ERROR_INVARIANT_CONTRACT_EMPTY")
    if len(set(statuses)) != len(statuses):
        raise ValueError("E_RESULT_ERROR_INVARIANT_CONTRACT_DUPLICATE_STATUS")
    if set(statuses) != _FAILURE_FORBIDDEN_STATUS_SET:
        raise ValueError("E_RESULT_ERROR_INVARIANT_CONTRACT_STATUS_SET_MISMATCH")
    return tuple(sorted(statuses))


def validate_result_error_invariant(
    *,
    status: str,
    failure_class: str | None = None,
    failure_reason: str | None = None,
) -> str:
    resolved_status = str(status or "").strip().lower()
    if not resolved_status:
        raise ValueError("E_RESULT_ERROR_INVARIANT:status_required")
    resolved_failure_class = str(failure_class or "").strip()
    resolved_failure_reason = str(failure_reason or "").strip()
    has_failure = bool(resolved_failure_class or resolved_failure_reason)

    if resolved_status in _FAILURE_FORBIDDEN_STATUS_SET and has_failure:
        raise ValueError(f"E_RESULT_ERROR_INVARIANT:{resolved_status}_must_not_have_failure")

    return resolved_status
