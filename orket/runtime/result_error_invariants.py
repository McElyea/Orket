from __future__ import annotations


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

    if resolved_status in {"done", "incomplete", "running"} and has_failure:
        raise ValueError(f"E_RESULT_ERROR_INVARIANT:{resolved_status}_must_not_have_failure")

    return resolved_status
