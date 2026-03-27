from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from orket.schema import CardStatus
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    CompletionClassification,
    ExecutionFailureClass,
    FailurePlane,
    ResultClass,
    SideEffectBoundaryClass,
    TruthFailureClass,
    RunState,
)


BLOCKED_CLOSEOUT_REASONS = {
    "dependency_blocked",
    "governance_violation",
    "missing_seat",
    "odr_prebuild_failed",
    "runtime_guard_terminal_failure",
    "team_replan_limit_exceeded",
}

FAILED_CLOSEOUT_REASONS = {
    "catastrophic_failure",
    "missing_role_asset",
    "retry_scheduled",
    "runtime_guard_retry_scheduled",
}


def holder_ref_for_issue(*, session_id: str, issue_id: str) -> str:
    return f"orchestrator-issue:{str(session_id).strip()}:{str(issue_id).strip()}"


def scheduler_holder_ref_for_issue(*, session_id: str, issue_id: str) -> str:
    return f"orchestrator-issue-scheduler:{str(session_id).strip()}:{str(issue_id).strip()}"


def child_workload_holder_ref_for_issue(*, session_id: str, issue_id: str) -> str:
    return f"orchestrator-child-workload:{str(session_id).strip()}:{str(issue_id).strip()}"


def run_id_for_dispatch(*, session_id: str, issue_id: str, seat_name: str, turn_index: int) -> str:
    return (
        f"orchestrator-issue-run:{str(session_id).strip()}:{str(issue_id).strip()}"
        f":{str(seat_name).strip()}:{int(turn_index):04d}"
    )


def reservation_id_for_run(*, run_id: str) -> str:
    return f"orchestrator-issue-reservation:{str(run_id).strip()}"


def lease_id_for_run(*, run_id: str) -> str:
    return f"orchestrator-issue-lease:{str(run_id).strip()}"


def attempt_id_for_run(*, run_id: str) -> str:
    return f"{run_id}:attempt:0001"


def resource_id(*, session_id: str, issue_id: str) -> str:
    return f"issue-dispatch-slot:{str(session_id).strip()}:{str(issue_id).strip()}"


def namespace_scope(*, issue_id: str) -> str:
    return f"issue:{str(issue_id).strip()}"


def namespace_resource_id(*, issue_id: str) -> str:
    return f"namespace:{namespace_scope(issue_id=issue_id)}"


def resources_touched(*, issue_id: str, related_issue_ids: list[str] | tuple[str, ...] = ()) -> list[str]:
    scope = namespace_scope(issue_id=issue_id)
    touched: list[str] = [f"issue:{str(issue_id).strip()}", f"namespace:{scope}"]
    for related_issue_id in related_issue_ids:
        normalized_issue_id = str(related_issue_id or "").strip()
        if not normalized_issue_id:
            continue
        resource_ref = f"issue:{normalized_issue_id}"
        if resource_ref not in touched:
            touched.append(resource_ref)
    return touched


def scheduler_run_id_for_transition(
    *,
    session_id: str,
    issue_id: str,
    current_status: CardStatus | str,
    target_status: CardStatus | str,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> str:
    normalized_reason = str(reason or "").strip().lower() or "unknown"
    token = digest(
        {
            "current_status": status_token(current_status),
            "target_status": status_token(target_status),
            "reason": normalized_reason,
            "metadata": dict(metadata or {}),
        }
    ).split(":", 1)[-1][:16]
    return (
        f"orchestrator-issue-scheduler-run:{str(session_id).strip()}:{str(issue_id).strip()}"
        f":{normalized_reason}:{token}"
    )


def child_workload_run_id_for_issue_creation(
    *,
    session_id: str,
    child_issue_id: str,
    relationship_class: str,
    metadata: dict[str, object] | None = None,
) -> str:
    normalized_relationship = str(relationship_class or "").strip().lower() or "child_workload"
    token = digest(
        {
            "relationship_class": normalized_relationship,
            "metadata": dict(metadata or {}),
        }
    ).split(":", 1)[-1][:16]
    return (
        f"orchestrator-child-workload-run:{str(session_id).strip()}:{str(child_issue_id).strip()}"
        f":{normalized_relationship}:{token}"
    )


def run_id_from_reservation_id(*, reservation_id: str) -> str:
    prefix = "orchestrator-issue-reservation:"
    normalized = str(reservation_id or "").strip()
    if not normalized.startswith(prefix):
        raise ValueError(f"unexpected orchestrator reservation id: {reservation_id}")
    return normalized[len(prefix) :]


def status_token(status: CardStatus | str) -> str:
    return str(status.value if hasattr(status, "value") else status).strip().lower() or "unknown"


def status_ref(*, session_id: str, issue_id: str, status: CardStatus | str) -> str:
    return f"issue-status:{str(session_id).strip()}:{str(issue_id).strip()}:{status_token(status)}"


def transition_ref(
    *,
    session_id: str,
    issue_id: str,
    from_status: CardStatus | str,
    to_status: CardStatus | str,
    reason: str,
) -> str:
    return (
        f"issue-transition:{str(session_id).strip()}:{str(issue_id).strip()}:"
        f"{status_token(from_status)}->{status_token(to_status)}:{str(reason).strip().lower() or 'unknown'}"
    )


def observation_ref(*, session_id: str, issue_id: str, status: CardStatus | str, reason: str) -> str:
    return (
        f"issue-observation:{str(session_id).strip()}:{str(issue_id).strip()}:"
        f"{status_token(status)}:{str(reason).strip().lower() or 'unknown'}"
    )


def issue_creation_ref(*, session_id: str, issue_id: str, relationship_class: str) -> str:
    return (
        f"issue-creation:{str(session_id).strip()}:{str(issue_id).strip()}:"
        f"{str(relationship_class).strip().lower() or 'child_workload'}"
    )


def digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def classify_closeout(
    *,
    target_status: CardStatus | str,
    reason: str,
) -> tuple[AttemptState, RunState, ResultClass, CompletionClassification, ClosureBasisClassification]:
    status_value = status_token(target_status)
    reason_token = str(reason or "").strip().lower()
    if status_value == CardStatus.CANCELED.value:
        return (
            AttemptState.ABANDONED,
            RunState.CANCELLED,
            ResultClass.BLOCKED,
            CompletionClassification.UNSATISFIED,
            ClosureBasisClassification.CANCELLED_BY_AUTHORITY,
        )
    if status_value in {CardStatus.BLOCKED.value, CardStatus.GUARD_REJECTED.value} or reason_token in BLOCKED_CLOSEOUT_REASONS:
        return (
            AttemptState.FAILED,
            RunState.FAILED_TERMINAL,
            ResultClass.BLOCKED,
            CompletionClassification.UNSATISFIED,
            ClosureBasisClassification.POLICY_TERMINAL_STOP,
        )
    if status_value == CardStatus.READY.value or reason_token in FAILED_CLOSEOUT_REASONS:
        return (
            AttemptState.FAILED,
            RunState.FAILED_TERMINAL,
            ResultClass.FAILED,
            CompletionClassification.UNSATISFIED,
            ClosureBasisClassification.NORMAL_EXECUTION,
        )
    return (
        AttemptState.COMPLETED,
        RunState.COMPLETED,
        ResultClass.SUCCESS,
        CompletionClassification.SATISFIED,
        ClosureBasisClassification.NORMAL_EXECUTION,
    )


def classify_terminal_recovery_failure(
    *,
    result_class: ResultClass,
    closure_basis: ClosureBasisClassification,
    reason: str,
) -> tuple[
    str,
    FailurePlane,
    ExecutionFailureClass | TruthFailureClass,
    SideEffectBoundaryClass,
]:
    normalized_reason = str(reason or "").strip().lower() or "unknown"
    if result_class is ResultClass.BLOCKED or closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP:
        return (
            f"orchestrator_issue_blocked:{normalized_reason}",
            FailurePlane.TRUTH,
            TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY,
            SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
        )
    return (
        f"orchestrator_issue_failed:{normalized_reason}",
        FailurePlane.EXECUTION,
        ExecutionFailureClass.ADAPTER_EXECUTION_FAILURE,
        SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
    )


__all__ = [
    "attempt_id_for_run",
    "classify_closeout",
    "classify_terminal_recovery_failure",
    "child_workload_holder_ref_for_issue",
    "child_workload_run_id_for_issue_creation",
    "digest",
    "holder_ref_for_issue",
    "issue_creation_ref",
    "lease_id_for_run",
    "namespace_resource_id",
    "namespace_scope",
    "observation_ref",
    "reservation_id_for_run",
    "resource_id",
    "resources_touched",
    "run_id_for_dispatch",
    "run_id_from_reservation_id",
    "scheduler_holder_ref_for_issue",
    "scheduler_run_id_for_transition",
    "status_ref",
    "status_token",
    "transition_ref",
    "utc_now",
]
