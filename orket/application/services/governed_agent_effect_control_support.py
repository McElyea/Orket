from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from orket.application.services.governed_agent_effect_records import approval_id
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult


def _resume_timings(
    *,
    request: AgentIterationRequest,
    decision: str,
    next_lease_expires_at_utc: str | None,
    decision_timestamps_utc: Sequence[str],
    next_lease_expiries_utc: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if decision != "approved":
        return (), ()
    if not str(next_lease_expires_at_utc or "").strip():
        raise ValueError("E_AGENT_EFFECT_RESUME_LEASE_REQUIRED")
    lease = datetime.fromisoformat(_utc_timestamp(next_lease_expires_at_utc).replace("Z", "+00:00"))
    deadline = datetime.fromisoformat(request.deadline_utc.replace("Z", "+00:00"))
    if lease > deadline:
        raise ValueError("E_AGENT_EFFECT_RESUME_LEASE_EXCEEDS_DEADLINE")
    decisions = tuple(_utc_timestamp(item) for item in decision_timestamps_utc)
    expiries = tuple(_utc_timestamp(item) for item in next_lease_expiries_utc)
    remaining_iterations = max(0, request.remaining_run_budget.iterations - 1)
    if len(decisions) < remaining_iterations or len(expiries) < max(0, remaining_iterations - 1):
        raise ValueError("E_AGENT_EFFECT_RESUME_TIMESTAMPS_INCOMPLETE")
    return decisions, expiries


def _utc_timestamp(value: object) -> str:
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("E_AGENT_EFFECT_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("E_AGENT_EFFECT_TIMESTAMP_NOT_UTC")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_run_approval(result: AgentIterationResult, approval_id_ref: str) -> None:
    valid_approvals = {
        approval_id(proposal)
        for proposal in result.effect_proposals
        if proposal.capability == "write_file"
    }
    if approval_id_ref not in valid_approvals:
        raise ValueError("E_AGENT_EFFECT_APPROVAL_RUN_MISMATCH")


def _required_text(value: object, code: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(code)
    return text


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _string_sequence(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("E_AGENT_EFFECT_TIMESTAMPS_INVALID")
    return tuple(value)
