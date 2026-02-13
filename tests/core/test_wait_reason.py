import pytest
from orket.schema import IssueConfig, CardStatus, WaitReason, CardType
from orket.domain.state_machine import StateMachine, StateMachineError


def test_wait_reason_enum_values():
    """Test that WaitReason has the expected values."""
    assert WaitReason.RESOURCE.value == "resource"
    assert WaitReason.DEPENDENCY.value == "dependency"
    assert WaitReason.REVIEW.value == "review"
    assert WaitReason.INPUT.value == "input"


def test_issue_config_accepts_wait_reason():
    """Test that IssueConfig accepts wait_reason field."""
    issue = IssueConfig(
        summary="Test issue",
        status=CardStatus.BLOCKED,
        wait_reason=WaitReason.RESOURCE
    )
    assert issue.wait_reason == WaitReason.RESOURCE


def test_issue_config_wait_reason_defaults_to_none():
    """Test that wait_reason defaults to None."""
    issue = IssueConfig(summary="Test issue")
    assert issue.wait_reason is None


def test_state_machine_requires_wait_reason_for_blocked():
    """Test that transitioning to BLOCKED requires a wait_reason."""
    with pytest.raises(StateMachineError, match="wait_reason is required"):
        StateMachine.validate_transition(
            card_type=CardType.ISSUE,
            current=CardStatus.IN_PROGRESS,
            requested=CardStatus.BLOCKED,
            wait_reason=None  # Missing wait_reason should raise error
        )


def test_state_machine_requires_wait_reason_for_waiting_for_developer():
    """Test that transitioning to WAITING_FOR_DEVELOPER requires a wait_reason."""
    with pytest.raises(StateMachineError, match="wait_reason is required"):
        StateMachine.validate_transition(
            card_type=CardType.ISSUE,
            current=CardStatus.IN_PROGRESS,
            requested=CardStatus.WAITING_FOR_DEVELOPER,
            wait_reason=None
        )


def test_state_machine_allows_blocked_with_wait_reason():
    """Test that BLOCKED transition succeeds when wait_reason is provided."""
    # Should not raise
    StateMachine.validate_transition(
        card_type=CardType.ISSUE,
        current=CardStatus.IN_PROGRESS,
        requested=CardStatus.BLOCKED,
        wait_reason=WaitReason.RESOURCE
    )


def test_state_machine_allows_waiting_with_wait_reason():
    """Test that WAITING_FOR_DEVELOPER transition succeeds with wait_reason."""
    # Should not raise
    StateMachine.validate_transition(
        card_type=CardType.ISSUE,
        current=CardStatus.IN_PROGRESS,
        requested=CardStatus.WAITING_FOR_DEVELOPER,
        wait_reason=WaitReason.DEPENDENCY
    )


def test_state_machine_does_not_require_wait_reason_for_other_states():
    """Test that wait_reason is not required for non-waiting states."""
    # Should not raise - wait_reason not required for READY_FOR_TESTING
    StateMachine.validate_transition(
        card_type=CardType.ISSUE,
        current=CardStatus.IN_PROGRESS,
        requested=CardStatus.READY_FOR_TESTING,
        wait_reason=None
    )

    # Should not raise - wait_reason not required for CODE_REVIEW
    StateMachine.validate_transition(
        card_type=CardType.ISSUE,
        current=CardStatus.IN_PROGRESS,
        requested=CardStatus.CODE_REVIEW,
        wait_reason=None
    )


def test_state_machine_allows_archive_from_done_issue():
    """Test that completed issues can be archived."""
    StateMachine.validate_transition(
        card_type=CardType.ISSUE,
        current=CardStatus.DONE,
        requested=CardStatus.ARCHIVED,
        wait_reason=None,
    )


def test_wait_reason_resource():
    """Test RESOURCE wait reason usage."""
    issue = IssueConfig(
        summary="Waiting for LLM slot",
        status=CardStatus.BLOCKED,
        wait_reason=WaitReason.RESOURCE
    )
    assert issue.wait_reason == WaitReason.RESOURCE
    assert issue.wait_reason.value == "resource"


def test_wait_reason_dependency():
    """Test DEPENDENCY wait reason usage."""
    issue = IssueConfig(
        summary="Waiting for parent card",
        status=CardStatus.BLOCKED,
        wait_reason=WaitReason.DEPENDENCY,
        depends_on=["PARENT-1"]
    )
    assert issue.wait_reason == WaitReason.DEPENDENCY
    assert len(issue.depends_on) == 1


def test_wait_reason_review():
    """Test REVIEW wait reason usage."""
    issue = IssueConfig(
        summary="Waiting for human review",
        status=CardStatus.WAITING_FOR_DEVELOPER,
        wait_reason=WaitReason.REVIEW
    )
    assert issue.wait_reason == WaitReason.REVIEW


def test_wait_reason_input():
    """Test INPUT wait reason usage."""
    issue = IssueConfig(
        summary="Waiting for clarification",
        status=CardStatus.WAITING_FOR_DEVELOPER,
        wait_reason=WaitReason.INPUT
    )
    assert issue.wait_reason == WaitReason.INPUT


def test_wait_reason_can_be_cleared():
    """Test that wait_reason can be set to None when unblocking."""
    issue = IssueConfig(
        summary="Test issue",
        status=CardStatus.BLOCKED,
        wait_reason=WaitReason.RESOURCE
    )

    # Simulate unblocking
    issue.status = CardStatus.IN_PROGRESS
    issue.wait_reason = None

    assert issue.status == CardStatus.IN_PROGRESS
    assert issue.wait_reason is None


def test_multiple_issues_with_different_wait_reasons():
    """Test that different issues can have different wait reasons."""
    issues = [
        IssueConfig(id="I1", summary="Needs VRAM", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE),
        IssueConfig(id="I2", summary="Needs parent", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY),
        IssueConfig(id="I3", summary="Needs review", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.REVIEW),
        IssueConfig(id="I4", summary="Needs input", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.INPUT),
    ]

    assert issues[0].wait_reason == WaitReason.RESOURCE
    assert issues[1].wait_reason == WaitReason.DEPENDENCY
    assert issues[2].wait_reason == WaitReason.REVIEW
    assert issues[3].wait_reason == WaitReason.INPUT

