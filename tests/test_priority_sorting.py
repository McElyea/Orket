import pytest
from orket.schema import EpicConfig, IssueConfig, CardStatus
from orket.domain.critical_path import CriticalPathEngine


def test_priority_field_migration_from_string():
    """Test that legacy string priorities are converted to floats."""
    issue_high = IssueConfig(summary="High priority", priority="High")
    issue_med = IssueConfig(summary="Medium priority", priority="Medium")
    issue_low = IssueConfig(summary="Low priority", priority="Low")

    assert issue_high.priority == 3.0
    assert issue_med.priority == 2.0
    assert issue_low.priority == 1.0


def test_priority_field_accepts_floats():
    """Test that numeric priorities are accepted directly."""
    issue = IssueConfig(summary="Custom priority", priority=2.5)
    assert issue.priority == 2.5


def test_priority_default_value():
    """Test that priority defaults to 2.0 (Medium)."""
    issue = IssueConfig(summary="Default priority")
    assert issue.priority == 2.0


def test_priority_queue_sorts_by_combined_score():
    """Test that queue sorts by base_priority + dependency_weight."""
    epic = EpicConfig(
        name="Test Epic",
        team="standard",
        environment="standard",
        issues=[
            IssueConfig(id="A", summary="Low priority, no deps", priority=1.0, status=CardStatus.READY),
            IssueConfig(id="B", summary="High priority, no deps", priority=3.0, status=CardStatus.READY),
            IssueConfig(id="C", summary="Medium priority, no deps", priority=2.0, status=CardStatus.READY),
        ]
    )

    queue = CriticalPathEngine.get_priority_queue(epic)

    # Should be sorted by priority: B (3.0), C (2.0), A (1.0)
    assert queue == ["B", "C", "A"]


def test_priority_queue_combines_priority_and_dependencies():
    """Test that dependency weight is added to base priority."""
    epic = EpicConfig(
        name="Test Epic",
        team="standard",
        environment="standard",
        issues=[
            IssueConfig(id="A", summary="Low priority but blocks B", priority=1.0, status=CardStatus.READY),
            IssueConfig(id="B", summary="High priority but blocked", priority=3.0, depends_on=["A"], status=CardStatus.READY),
            IssueConfig(id="C", summary="Medium priority, no deps", priority=2.0, status=CardStatus.READY),
        ]
    )

    queue = CriticalPathEngine.get_priority_queue(epic)

    # Scores:
    # A has score = 1.0 (priority) + 1 (blocks B) = 2.0
    # B has score = 3.0 (priority) + 0 (blocks nothing) = 3.0
    # C has score = 2.0 (priority) + 0 (blocks nothing) = 2.0
    # Order: B (3.0), A (2.0), C (2.0)
    assert queue == ["B", "A", "C"]


def test_priority_queue_ignores_non_ready_cards():
    """Test that only READY cards appear in the priority queue."""
    epic = EpicConfig(
        name="Test Epic",
        team="standard",
        environment="standard",
        issues=[
            IssueConfig(id="A", summary="Ready", priority=3.0, status=CardStatus.READY),
            IssueConfig(id="B", summary="In Progress", priority=3.0, status=CardStatus.IN_PROGRESS),
            IssueConfig(id="C", summary="Done", priority=3.0, status=CardStatus.DONE),
            IssueConfig(id="D", summary="Blocked", priority=3.0, status=CardStatus.BLOCKED),
        ]
    )

    queue = CriticalPathEngine.get_priority_queue(epic)

    # Only A should be in the queue
    assert queue == ["A"]


def test_priority_queue_high_weight_beats_high_priority():
    """Test that a low-priority card blocking many others gets prioritized."""
    epic = EpicConfig(
        name="Test Epic",
        team="standard",
        environment="standard",
        issues=[
            # Foundation card: low priority but blocks 3 others
            IssueConfig(id="FOUND", summary="Foundation", priority=1.0, status=CardStatus.READY),

            # High priority card but doesn't block anything
            IssueConfig(id="HIGH", summary="High but isolated", priority=3.0, status=CardStatus.READY),

            # Three cards that depend on FOUND
            IssueConfig(id="DEP1", summary="Depends on FOUND", depends_on=["FOUND"]),
            IssueConfig(id="DEP2", summary="Depends on FOUND", depends_on=["FOUND"]),
            IssueConfig(id="DEP3", summary="Depends on FOUND", depends_on=["FOUND"]),
        ]
    )

    queue = CriticalPathEngine.get_priority_queue(epic)

    # FOUND has score = 1.0 (priority) + 3 (blocks DEP1, DEP2, DEP3) = 4.0
    # HIGH has score = 3.0 (priority) + 0 (blocks nothing) = 3.0
    # FOUND should come first despite lower priority
    assert queue[0] == "FOUND"
    assert queue[1] == "HIGH"


def test_priority_migration_case_insensitive():
    """Test that priority string migration is case-insensitive."""
    issue_upper = IssueConfig(summary="Test", priority="HIGH")
    issue_lower = IssueConfig(summary="Test", priority="low")
    issue_mixed = IssueConfig(summary="Test", priority="MeDiUm")

    assert issue_upper.priority == 3.0
    assert issue_lower.priority == 1.0
    assert issue_mixed.priority == 2.0
