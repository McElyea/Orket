# Layer: contract

from __future__ import annotations

import pytest

from orket.core.domain.sandbox_lifecycle import (
    CleanupState,
    LifecycleEvent,
    OwnershipConfidence,
    ReconciliationClassification,
    SandboxLifecycleError,
    SandboxState,
    TerminalReason,
    classify_reconciliation,
    validate_cleanup_state_transition,
    validate_lifecycle_transition,
)


@pytest.mark.parametrize(
    ("current_state", "event", "next_state", "terminal_reason", "cleanup_state"),
    [
        (SandboxState.CREATING, LifecycleEvent.CREATE_ACCEPTED, SandboxState.STARTING, None, None),
        (
            SandboxState.CREATING,
            LifecycleEvent.CREATE_FAILURE,
            SandboxState.TERMINAL,
            TerminalReason.CREATE_FAILED,
            None,
        ),
        (SandboxState.STARTING, LifecycleEvent.HEALTH_VERIFIED, SandboxState.ACTIVE, None, None),
        (
            SandboxState.STARTING,
            LifecycleEvent.STARTUP_FAILURE,
            SandboxState.TERMINAL,
            TerminalReason.START_FAILED,
            None,
        ),
        (
            SandboxState.STARTING,
            LifecycleEvent.LEASE_EXPIRED,
            SandboxState.RECLAIMABLE,
            TerminalReason.LEASE_EXPIRED,
            None,
        ),
        (
            SandboxState.ACTIVE,
            LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME,
            SandboxState.TERMINAL,
            TerminalReason.SUCCESS,
            None,
        ),
        (
            SandboxState.ACTIVE,
            LifecycleEvent.LEASE_EXPIRED,
            SandboxState.RECLAIMABLE,
            TerminalReason.LEASE_EXPIRED,
            None,
        ),
        (
            SandboxState.ACTIVE,
            LifecycleEvent.HARD_MAX_AGE_REACHED,
            SandboxState.TERMINAL,
            TerminalReason.HARD_MAX_AGE,
            None,
        ),
        (
            SandboxState.RECLAIMABLE,
            LifecycleEvent.OWNERSHIP_REACQUIRED,
            SandboxState.ACTIVE,
            None,
            None,
        ),
        (
            SandboxState.RECLAIMABLE,
            LifecycleEvent.RECLAIM_TTL_ELAPSED,
            SandboxState.TERMINAL,
            TerminalReason.LEASE_EXPIRED,
            None,
        ),
        (
            SandboxState.TERMINAL,
            LifecycleEvent.CLEANUP_SCHEDULED,
            SandboxState.TERMINAL,
            None,
            CleanupState.SCHEDULED,
        ),
        (
            SandboxState.TERMINAL,
            LifecycleEvent.CLEANUP_STARTS,
            SandboxState.TERMINAL,
            None,
            CleanupState.IN_PROGRESS,
        ),
        (
            SandboxState.TERMINAL,
            LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            SandboxState.CLEANED,
            None,
            CleanupState.COMPLETED,
        ),
        (
            SandboxState.ORPHANED,
            LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            SandboxState.CLEANED,
            None,
            CleanupState.COMPLETED,
        ),
    ],
)
def test_lifecycle_transition_matrix_accepts_required_transitions(
    current_state: SandboxState,
    event: LifecycleEvent,
    next_state: SandboxState,
    terminal_reason: TerminalReason | None,
    cleanup_state: CleanupState | None,
) -> None:
    assert (
        validate_lifecycle_transition(
            current_state=current_state,
            event=event,
            next_state=next_state,
            terminal_reason=terminal_reason,
            cleanup_state=cleanup_state,
        )
        is True
    )


@pytest.mark.parametrize(
    ("current_state", "event", "next_state", "terminal_reason", "cleanup_state"),
    [
        (SandboxState.CREATING, LifecycleEvent.CLEANUP_STARTS, SandboxState.TERMINAL, None, CleanupState.IN_PROGRESS),
        (SandboxState.ACTIVE, LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME, SandboxState.TERMINAL, None, None),
        (
            SandboxState.ACTIVE,
            LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME,
            SandboxState.TERMINAL,
            TerminalReason.CREATE_FAILED,
            None,
        ),
        (
            SandboxState.TERMINAL,
            LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            SandboxState.CLEANED,
            None,
            CleanupState.IN_PROGRESS,
        ),
        (SandboxState.RECLAIMABLE, LifecycleEvent.OWNERSHIP_REACQUIRED, SandboxState.CLEANED, None, None),
    ],
)
def test_lifecycle_transition_matrix_rejects_forbidden_transitions(
    current_state: SandboxState,
    event: LifecycleEvent,
    next_state: SandboxState,
    terminal_reason: TerminalReason | None,
    cleanup_state: CleanupState | None,
) -> None:
    with pytest.raises(SandboxLifecycleError):
        validate_lifecycle_transition(
            current_state=current_state,
            event=event,
            next_state=next_state,
            terminal_reason=terminal_reason,
            cleanup_state=cleanup_state,
        )


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (CleanupState.NONE, CleanupState.SCHEDULED),
        (CleanupState.SCHEDULED, CleanupState.IN_PROGRESS),
        (CleanupState.IN_PROGRESS, CleanupState.COMPLETED),
        (CleanupState.IN_PROGRESS, CleanupState.FAILED),
        (CleanupState.FAILED, CleanupState.SCHEDULED),
    ],
)
def test_cleanup_state_progression_accepts_monotonic_or_retry_safe_paths(
    current_state: CleanupState,
    next_state: CleanupState,
) -> None:
    assert validate_cleanup_state_transition(current_state=current_state, next_state=next_state) is True


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (CleanupState.NONE, CleanupState.IN_PROGRESS),
        (CleanupState.COMPLETED, CleanupState.SCHEDULED),
        (CleanupState.COMPLETED, CleanupState.FAILED),
        (CleanupState.SCHEDULED, CleanupState.COMPLETED),
    ],
)
def test_cleanup_state_progression_rejects_backwards_or_skipped_paths(
    current_state: CleanupState,
    next_state: CleanupState,
) -> None:
    with pytest.raises(SandboxLifecycleError):
        validate_cleanup_state_transition(current_state=current_state, next_state=next_state)


@pytest.mark.parametrize(
    ("durable_state", "docker_present", "ownership_confidence", "lease_expired", "cleanup_due_passed", "classification"),
    [
        (SandboxState.ACTIVE, True, None, False, False, ReconciliationClassification.ACTIVE),
        (SandboxState.ACTIVE, True, None, True, False, ReconciliationClassification.RECLAIMABLE),
        (SandboxState.ACTIVE, False, None, False, False, ReconciliationClassification.TERMINAL_LOST_RUNTIME),
        (SandboxState.TERMINAL, True, None, False, False, ReconciliationClassification.TERMINAL_AWAITING_CLEANUP),
        (SandboxState.TERMINAL, True, None, False, True, ReconciliationClassification.CLEANUP_OVERDUE),
        (SandboxState.TERMINAL, False, None, False, False, ReconciliationClassification.CLEANED_EXTERNALLY),
        (None, True, OwnershipConfidence.VERIFIED, False, False, ReconciliationClassification.ORPHANED_VERIFIED),
        (None, True, OwnershipConfidence.UNVERIFIED, False, False, ReconciliationClassification.ORPHANED_UNVERIFIED),
    ],
)
def test_reconciliation_matrix_classifies_required_cases(
    durable_state: SandboxState | None,
    docker_present: bool,
    ownership_confidence: OwnershipConfidence | None,
    lease_expired: bool,
    cleanup_due_passed: bool,
    classification: ReconciliationClassification,
) -> None:
    outcome = classify_reconciliation(
        durable_state=durable_state,
        docker_present=docker_present,
        ownership_confidence=ownership_confidence,
        lease_expired=lease_expired,
        cleanup_due_passed=cleanup_due_passed,
    )
    assert outcome.classification is classification

