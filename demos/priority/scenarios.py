from orket.schema import EpicConfig, IssueConfig, CardStatus
from orket.domain.critical_path import CriticalPathEngine

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_issue_table(epic):
    """Pretty print issues with their scores."""
    # Calculate weights
    blocked_by_me = {i.id: set() for i in epic.issues}
    for issue in epic.issues:
        for dep_id in issue.depends_on:
            if dep_id in blocked_by_me:
                blocked_by_me[dep_id].add(issue.id)

    weights = {}
    for issue_id in blocked_by_me:
        weights[issue_id] = CriticalPathEngine._calculate_weight(issue_id, blocked_by_me)

    # Print table header
    print(f"\n{'ID':<10} {'Priority':<10} {'Weight':<10} {'Score':<10} {'Status':<15} {'Summary':<30}")
    print('-' * 95)

    # Print each issue
    for issue in epic.issues:
        weight = weights.get(issue.id, 0)
        score = issue.priority + weight
        status_color = issue.status.value
        name = issue.name or "Untitled"
        print(f"{issue.id:<10} {issue.priority:<10.1f} {weight:<10} {score:<10.1f} {status_color:<15} {name[:30]:<30}")

def run_basic_scenario():
    """Scenario 1: Simple priority ordering (no dependencies)"""
    print_section("Scenario 1: Basic Priority (No Dependencies)")

    epic = EpicConfig(
        name="Feature Launch",
        team="standard",
        environment="standard",
        issues=[
            IssueConfig(id="LOW", summary="Nice to have feature", priority=1.0, status=CardStatus.READY),
            IssueConfig(id="MED", summary="Standard feature", priority=2.0, status=CardStatus.READY),
            IssueConfig(id="HIGH", summary="Critical security fix", priority=3.0, status=CardStatus.READY),
            IssueConfig(id="CUSTOM", summary="Custom priority task", priority=2.5, status=CardStatus.READY),
        ]
    )

    print("\nIssue Details:")
    print_issue_table(epic)

    queue = CriticalPathEngine.get_priority_queue(epic)

    print("\n>> Execution Queue Order:")
    for idx, issue_id in enumerate(queue, 1):
        issue = next(i for i in epic.issues if i.id == issue_id)
        print(f"  {idx}. {issue_id} (score: {issue.priority:.1f}) - {issue.name}")

def run_dependency_scenario():
    """Scenario 2: Priority + Dependency weighting"""
    print_section("Scenario 2: Priority + Dependency Weight")

    epic = EpicConfig(
        name="API Refactor",
        team="standard",
        environment="standard",
        issues=[
            # Foundation: Low priority but blocks everything
            IssueConfig(
                id="SCHEMA",
                summary="Update database schema",
                priority=1.0,  # Low priority
                status=CardStatus.READY
            ),

            # Mid-tier: Depends on SCHEMA, blocks APP
            IssueConfig(
                id="API",
                summary="Refactor API endpoints",
                priority=2.0,
                depends_on=["SCHEMA"],
                status=CardStatus.READY  # Artificially READY to show scoring
            ),

            # Top-tier: Depends on API
            IssueConfig(
                id="APP",
                summary="Update frontend app",
                priority=3.0,
                depends_on=["API"],
                status=CardStatus.READY
            ),

            # Isolated: High priority but blocks nothing
            IssueConfig(
                id="DOCS",
                summary="Update documentation",
                priority=2.5,
                status=CardStatus.READY
            ),
        ]
    )

    print("\nIssue Details:")
    print_issue_table(epic)

    print("\n** Explanation:")
    print("  - SCHEMA: priority=1.0, but blocks API and APP (recursively) -> weight=2 -> score=3.0")
    print("  - API: priority=2.0, blocks APP -> weight=1 -> score=3.0")
    print("  - APP: priority=3.0, blocks nothing -> weight=0 -> score=3.0")
    print("  - DOCS: priority=2.5, blocks nothing -> weight=0 -> score=2.5")

    queue = CriticalPathEngine.get_priority_queue(epic)

    print("\n>> Execution Queue Order:")
    for idx, issue_id in enumerate(queue, 1):
        issue = next(i for i in epic.issues if i.id == issue_id)
        weights = {
            "SCHEMA": 2, "API": 1, "APP": 0, "DOCS": 0
        }
        score = issue.priority + weights.get(issue_id, 0)
        print(f"  {idx}. {issue_id:<10} (score: {score:.1f}) - {issue.name}")

    print("\n** Notice: SCHEMA wins despite lowest priority!")
