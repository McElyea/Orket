#!/usr/bin/env python3
"""
Test drive for v0.3.9 Wait Reason
Demonstrates how wait_reason helps diagnose bottlenecks.
"""

from orket.schema import EpicConfig, IssueConfig, CardStatus, WaitReason, BottleneckThresholds
from collections import Counter


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_issue_report(issues, title="Issue Status"):
    """Pretty print issues with their wait reasons."""
    print(f"\n{title}:")
    print(f"{'ID':<12} {'Status':<20} {'Wait Reason':<15} {'Summary':<30}")
    print('-' * 80)

    for issue in issues:
        wait = issue.wait_reason.value if issue.wait_reason else "-"
        name = issue.name or "Untitled"
        print(f"{issue.id:<12} {issue.status.value:<20} {wait:<15} {name[:30]:<30}")


def analyze_bottlenecks(issues, thresholds=None):
    """
    Smarter bottleneck analysis with configurable thresholds.
    Distinguishes normal operation from real problems.
    """
    if thresholds is None:
        thresholds = BottleneckThresholds()

    blocked = [i for i in issues if i.status in {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER}]
    active = [i for i in issues if i.status == CardStatus.IN_PROGRESS]

    if not blocked:
        print("\n** Status: Healthy")
        print(f"   {len(active)} active, 0 blocked - work is flowing smoothly")
        return

    wait_counts = Counter(i.wait_reason for i in blocked if i.wait_reason)
    resource_blocked = wait_counts.get(WaitReason.RESOURCE, 0)
    dependency_blocked = wait_counts.get(WaitReason.DEPENDENCY, 0)
    human_blocked = wait_counts.get(WaitReason.REVIEW, 0) + wait_counts.get(WaitReason.INPUT, 0)

    print(f"\n** Status: {len(blocked)} blocked, {len(active)} active")
    print(f"\n   Breakdown by wait_reason:")
    for reason, count in wait_counts.most_common():
        pct = (count / len(blocked)) * 100
        print(f"     - {reason.value:<15}: {count:>2} cards ({pct:>5.1f}%)")

    # Diagnosis with thresholds
    print(f"\n** Diagnosis:")

    # Resource blocking
    if resource_blocked > 0:
        if len(active) > 0 and resource_blocked <= thresholds.resource_normal:
            print(f"   OK: {resource_blocked} card(s) queued (normal serial execution)")
        elif len(active) == 0:
            print(f"   CRITICAL: {resource_blocked} blocked but nothing running!")
            print("   ACTION: Check resource allocation - cards blocked but no work in progress")
        elif resource_blocked >= thresholds.resource_critical:
            print(f"   CRITICAL: Large queue ({resource_blocked} cards) - chronic bottleneck!")
            print("   ACTION: Add more LLM capacity or reduce concurrency")
        elif resource_blocked >= thresholds.resource_warning:
            print(f"   WARNING: Queue building up ({resource_blocked} cards)")
            print("   ACTION: Monitor queue depth, consider scaling if it persists")

    # Dependency blocking
    if dependency_blocked > 0:
        dep_pct = dependency_blocked / len(blocked)
        if dep_pct >= thresholds.dependency_warning_pct:
            print(f"   ATTENTION: Dependency pile-up ({dependency_blocked} cards)")
            print("   ACTION: Prioritize foundation cards to unblock dependents")

    # Human attention
    if human_blocked >= thresholds.human_attention_threshold:
        print(f"   HUMAN REQUIRED: {human_blocked} card(s) need review/input")
        print("   ACTION: Review pending cards and provide input/approval")


def scenario_1_resource_constrained():
    """Scenario 1: VRAM maxed out - everything waiting for resources"""
    print_section("Scenario 1: Resource Constraint (VRAM Maxed)")

    issues = [
        IssueConfig(id="ACTIVE", summary="Currently running", status=CardStatus.IN_PROGRESS),
        IssueConfig(id="WAIT-1", summary="High priority task", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE, priority=3.0),
        IssueConfig(id="WAIT-2", summary="Medium priority task", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE, priority=2.0),
        IssueConfig(id="WAIT-3", summary="Low priority task", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE, priority=1.0),
        IssueConfig(id="READY", summary="Not started yet", status=CardStatus.READY),
    ]

    print_issue_report(issues)
    analyze_bottlenecks(issues)

    print(f"\n** What's Happening:")
    print("   - ACTIVE is consuming the only available LLM slot")
    print("   - 3 high-value cards are queued, waiting for resources to free up")
    print("   - Priority queue will process WAIT-1 next (highest priority)")


def scenario_2_dependency_pile_up():
    """Scenario 2: Foundation card not done - everything blocked"""
    print_section("Scenario 2: Dependency Pile-Up")

    issues = [
        IssueConfig(id="FOUND", summary="Database schema update", status=CardStatus.IN_PROGRESS),
        IssueConfig(id="API-1", summary="Update API endpoints", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["FOUND"]),
        IssueConfig(id="API-2", summary="Add new endpoints", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["FOUND"]),
        IssueConfig(id="APP", summary="Update frontend", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["API-1"]),
        IssueConfig(id="TESTS", summary="Integration tests", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["API-1", "API-2"]),
    ]

    print_issue_report(issues)
    analyze_bottlenecks(issues)

    print(f"\n** What's Happening:")
    print("   - FOUND is the foundation - everything depends on it")
    print("   - 4 cards are blocked waiting for FOUND to complete")
    print("   - This is why priority system boosts foundation cards automatically")


def scenario_3_needs_human():
    """Scenario 3: Human intervention required"""
    print_section("Scenario 3: Human Intervention Required")

    issues = [
        IssueConfig(id="DONE-1", summary="Feature A complete", status=CardStatus.DONE),
        IssueConfig(id="DONE-2", summary="Feature B complete", status=CardStatus.DONE),
        IssueConfig(id="REVIEW-1", summary="Feature A needs approval", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.REVIEW),
        IssueConfig(id="REVIEW-2", summary="Feature B needs approval", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.REVIEW),
        IssueConfig(id="INPUT-1", summary="Unclear requirements", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.INPUT),
    ]

    print_issue_report(issues)
    analyze_bottlenecks(issues)

    print(f"\n** What's Happening:")
    print("   - Code work is done, but cards can't progress without human action")
    print("   - 2 cards need review/approval before moving to DONE")
    print("   - 1 card needs clarification before work can continue")


def scenario_4_mixed_bottlenecks():
    """Scenario 4: Multiple bottleneck types"""
    print_section("Scenario 4: Mixed Bottlenecks (Realistic Sprint)")

    issues = [
        # Active work
        IssueConfig(id="S4-1", summary="Login refactor", status=CardStatus.IN_PROGRESS),

        # Resource constrained
        IssueConfig(id="S4-2", summary="Payment processing", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE, priority=3.0),
        IssueConfig(id="S4-3", summary="Email notifications", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE, priority=2.0),

        # Dependency blocked
        IssueConfig(id="S4-4", summary="OAuth integration", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["S4-1"]),
        IssueConfig(id="S4-5", summary="2FA setup", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY, depends_on=["S4-1"]),

        # Needs human
        IssueConfig(id="S4-6", summary="API design review", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.REVIEW),
        IssueConfig(id="S4-7", summary="Unclear user story", status=CardStatus.WAITING_FOR_DEVELOPER, wait_reason=WaitReason.INPUT),

        # Ready to go
        IssueConfig(id="S4-8", summary="Update docs", status=CardStatus.READY),
        IssueConfig(id="S4-9", summary="Fix typo", status=CardStatus.READY),
    ]

    print_issue_report(issues)
    analyze_bottlenecks(issues)

    print(f"\n** What's Happening:")
    print("   - Diverse bottlenecks: resources, dependencies, and human attention")
    print("   - No single dominant blocker - this is typical of a healthy sprint")
    print("   - Action items span different domains (infra, planning, review)")


def scenario_5_unblocking():
    """Scenario 5: Demonstrating unblocking flow"""
    print_section("Scenario 5: Unblocking Flow")

    print("\n** Initial State: All blocked")
    issues = [
        IssueConfig(id="T1", summary="Task 1", status=CardStatus.BLOCKED, wait_reason=WaitReason.RESOURCE),
        IssueConfig(id="T2", summary="Task 2", status=CardStatus.BLOCKED, wait_reason=WaitReason.DEPENDENCY),
        IssueConfig(id="T3", summary="Task 3", status=CardStatus.BLOCKED, wait_reason=WaitReason.REVIEW),
    ]
    print_issue_report(issues, title="Before Unblocking")

    print("\n** Action: Unblock cards")
    print("   - T1: Resource freed up -> move to IN_PROGRESS, clear wait_reason")
    print("   - T2: Dependency completed -> move to READY, clear wait_reason")
    print("   - T3: Review approved -> move to IN_PROGRESS, clear wait_reason")

    # Simulate unblocking
    issues[0].status = CardStatus.IN_PROGRESS
    issues[0].wait_reason = None

    issues[1].status = CardStatus.READY
    issues[1].wait_reason = None

    issues[2].status = CardStatus.IN_PROGRESS
    issues[2].wait_reason = None

    print_issue_report(issues, title="After Unblocking")

    print(f"\n** Result:")
    print("   - All cards are now actively flowing (no more blocked cards)")
    print("   - wait_reason cleared when conditions resolved")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  >> Orket v0.3.9 Wait Reason Test Drive")
    print("="*60)

    scenario_1_resource_constrained()
    scenario_2_dependency_pile_up()
    scenario_3_needs_human()
    scenario_4_mixed_bottlenecks()
    scenario_5_unblocking()

    print("\n" + "="*60)
    print("  >> Test Drive Complete!")
    print("="*60)
    print("\nKey Takeaways:")
    print("  1. wait_reason makes blocking explicit and diagnosable")
    print("  2. Different wait_reasons require different unblocking strategies")
    print("  3. Bottleneck analysis helps identify systemic issues")
    print("  4. RESOURCE bottlenecks -> infrastructure problem")
    print("  5. DEPENDENCY bottlenecks -> prioritization problem")
    print("  6. REVIEW/INPUT bottlenecks -> human attention problem")
    print()
