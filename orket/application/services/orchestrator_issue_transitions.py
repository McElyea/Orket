"""Issue transition validation and local projections; storage/publication remain with their owners."""

from typing import Any

from orket.core.domain.workitem_transition import WorkItemTransitionService
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus, IssueConfig, WaitReason


def normalize_wait_reason_token(value: Any) -> str | None:
    if value is None:
        return None
    token = value.value if hasattr(value, "value") else value
    normalized = str(token).strip().lower()
    return normalized or None


def set_issue_runtime_retry_note(issue: IssueConfig, note: str | None) -> None:
    params = dict(getattr(issue, "params", None) or {})
    token = str(note or "").strip()
    if token:
        params["runtime_retry_note"] = token
    else:
        params.pop("runtime_retry_note", None)
    issue.params = params


def clear_issue_runtime_retry_note(issue: IssueConfig) -> None:
    set_issue_runtime_retry_note(issue, None)


def resolve_transition_wait_reason(
    *, target_status: CardStatus, reason: str, metadata: dict[str, Any] | None
) -> str | None:
    if isinstance(metadata, dict):
        explicit = normalize_wait_reason_token(metadata.get("wait_reason"))
        if explicit is not None:
            return explicit
    if target_status == CardStatus.BLOCKED:
        mapping = {
            "dependency_blocked": WaitReason.DEPENDENCY.value,
            "runtime_guard_terminal_failure": WaitReason.REVIEW.value,
            "catastrophic_failure": WaitReason.SYSTEM.value,
            "governance_violation": WaitReason.SYSTEM.value,
            "team_replan_limit_exceeded": WaitReason.SYSTEM.value,
        }
        return mapping.get(reason, WaitReason.SYSTEM.value)
    return None


def apply_issue_transition_locally(
    *, issue: IssueConfig, target_status: CardStatus, assignee: str | None, wait_reason: str | None
) -> None:
    issue.status = target_status
    if assignee is not None and hasattr(issue, "assignee"):
        issue.assignee = assignee
    if hasattr(issue, "wait_reason"):
        issue.wait_reason = WaitReason(wait_reason) if wait_reason else None


def validate_issue_transition(
    *,
    issue: IssueConfig,
    current_status: CardStatus,
    target_status: CardStatus,
    reason: str,
    roles: list[str] | None,
    wait_reason: str | None,
    allow_policy_override: bool,
    workflow_profile: str,
) -> None:
    transition_service = WorkItemTransitionService(workflow_profile=workflow_profile)
    payload = {"status": target_status.value, "wait_reason": wait_reason}
    transition = transition_service.request_transition(
        action="set_status", current_status=current_status, payload=payload, roles=roles or ["system"]
    )
    if not transition.ok and allow_policy_override:
        transition = transition_service.request_transition(
            action="system_set_status",
            current_status=current_status,
            payload={"status": target_status.value, "reason": reason, "wait_reason": wait_reason},
            roles=["system"],
        )
    if not transition.ok:
        raise ExecutionFailed(
            f"Transition rejected for issue {issue.id}: {(transition.error_code.value if transition.error_code else 'UNKNOWN')} {transition.error or ''}".strip()
        )
