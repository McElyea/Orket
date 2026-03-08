from __future__ import annotations

from pathlib import Path

from orket.core.domain.workitem_transition import (
    TransitionErrorCode,
    WorkItemTransitionService,
)
from orket.schema import CardStatus


def test_workitem_transition_requires_action_api() -> None:
    service = WorkItemTransitionService()
    result = service.request_transition(action="", current_status=CardStatus.READY)
    assert result.ok is False
    assert result.error_code == TransitionErrorCode.INVALID_ACTION

    success = service.request_transition(
        action="set_status",
        current_status=CardStatus.READY,
        payload={"status": "in_progress"},
    )
    assert success.ok is True
    assert success.new_status == "in_progress"


def test_executor_cannot_set_status_directly() -> None:
    source = Path("orket/application/workflows/turn_executor.py").read_text(encoding="utf-8")
    assert ".update_status(" not in source
    assert "issue.status =" not in source


def test_legacy_cards_profile_parity() -> None:
    service = WorkItemTransitionService(workflow_profile="legacy_cards_v1")
    to_review = service.request_transition(
        action="set_status",
        current_status=CardStatus.IN_PROGRESS,
        payload={"status": "code_review"},
        roles=["coder"],
    )
    assert to_review.ok is True
    assert to_review.new_status == "code_review"


def test_legacy_cards_profile_allows_review_retry_to_ready() -> None:
    """Layer: contract. Verifies review-stage retries can return an issue to the build queue."""
    service = WorkItemTransitionService(workflow_profile="legacy_cards_v1")
    retry = service.request_transition(
        action="set_status",
        current_status=CardStatus.CODE_REVIEW,
        payload={"status": "ready"},
        roles=["developer"],
    )
    assert retry.ok is True
    assert retry.new_status == "ready"


def test_project_task_profile_core_flow() -> None:
    service = WorkItemTransitionService(workflow_profile="project_task_v1")
    start = service.request_transition(
        action="set_status",
        current_status=CardStatus.READY,
        payload={"status": "in_progress"},
    )
    assert start.ok is True
    assert start.new_status == "in_progress"

    finish = service.request_transition(
        action="set_status",
        current_status=CardStatus.IN_PROGRESS,
        payload={"status": "done"},
    )
    assert finish.ok is True
    assert finish.new_status == "done"


def test_gate_runs_pre_and_post_transition() -> None:
    calls: list[str] = []

    class _GateBoundary:
        def pre_transition(self, **kwargs):
            calls.append("pre")
            return None

        def post_transition(self, **kwargs):
            calls.append("post")
            return None

    service = WorkItemTransitionService(
        workflow_profile="project_task_v1",
        gate_boundary=_GateBoundary(),
    )
    result = service.request_transition(
        action="set_status",
        current_status=CardStatus.READY,
        payload={"status": "in_progress"},
    )
    assert result.ok is True
    assert calls == ["pre", "post"]


def test_system_set_status_requires_reason_and_records_override_metadata() -> None:
    """Layer: contract. Verifies override requests still require an audit reason and preserve audit metadata."""
    service = WorkItemTransitionService(workflow_profile="legacy_cards_v1")
    missing_reason = service.request_transition(
        action="system_set_status",
        current_status=CardStatus.READY,
        payload={"status": "blocked"},
    )
    assert missing_reason.ok is False
    assert missing_reason.error_code == TransitionErrorCode.INVARIANT_FAILED

    overridden = service.request_transition(
        action="system_set_status",
        current_status=CardStatus.IN_PROGRESS,
        payload={"status": "blocked", "reason": "dependency_blocked", "wait_reason": "dependency"},
        roles=["developer"],
    )
    assert overridden.ok is True
    assert overridden.new_status == "blocked"
    assert overridden.metadata.get("policy_override") is True
    assert overridden.metadata.get("override_reason") == "dependency_blocked"


def test_system_set_status_enforces_transition_rules() -> None:
    """Layer: contract. Verifies override requests cannot bypass the workflow/state-machine transition rules."""
    service = WorkItemTransitionService(workflow_profile="legacy_cards_v1")
    rejected = service.request_transition(
        action="system_set_status",
        current_status=CardStatus.READY,
        payload={"status": "done", "reason": "force_complete"},
        roles=["system"],
    )
    assert rejected.ok is False
    assert rejected.error_code == TransitionErrorCode.POLICY_VIOLATION
    assert "invalid transition" in str(rejected.error).lower()


def test_system_set_status_runs_gate_boundaries_for_allowed_transitions() -> None:
    """Layer: contract. Verifies override requests still pass through the transition boundary hooks."""
    calls: list[str] = []

    class _GateBoundary:
        def pre_transition(self, **kwargs):
            calls.append("pre")
            return None

        def post_transition(self, **kwargs):
            calls.append("post")
            return None

    service = WorkItemTransitionService(
        workflow_profile="legacy_cards_v1",
        gate_boundary=_GateBoundary(),
    )
    result = service.request_transition(
        action="system_set_status",
        current_status=CardStatus.IN_PROGRESS,
        payload={"status": "blocked", "reason": "dependency_blocked", "wait_reason": "dependency"},
        roles=["developer"],
    )

    assert result.ok is True
    assert calls == ["pre", "post"]
