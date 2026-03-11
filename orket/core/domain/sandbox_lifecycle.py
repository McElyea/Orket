from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SandboxLifecycleError(ValueError):
    """Raised when sandbox lifecycle rules are violated."""


class SandboxState(str, Enum):
    CREATING = "creating"
    STARTING = "starting"
    ACTIVE = "active"
    TERMINAL = "terminal"
    RECLAIMABLE = "reclaimable"
    ORPHANED = "orphaned"
    CLEANED = "cleaned"


class CleanupState(str, Enum):
    NONE = "none"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TerminalReason(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELED = "canceled"
    CREATE_FAILED = "create_failed"
    START_FAILED = "start_failed"
    RESTART_LOOP = "restart_loop"
    LEASE_EXPIRED = "lease_expired"
    LOST_RUNTIME = "lost_runtime"
    ORPHAN_DETECTED = "orphan_detected"
    ORPHAN_UNVERIFIED_OWNERSHIP = "orphan_unverified_ownership"
    HARD_MAX_AGE = "hard_max_age"
    CLEANED_EXTERNALLY = "cleaned_externally"


class LifecycleEvent(str, Enum):
    CREATE_ACCEPTED = "create accepted"
    CREATE_FAILURE = "create failure"
    HEALTH_VERIFIED = "health verified"
    STARTUP_FAILURE = "startup failure"
    RUNTIME_MISSING = "runtime missing"
    LEASE_EXPIRED = "lease expired"
    WORKFLOW_TERMINAL_OUTCOME = "workflow terminal outcome"
    HARD_MAX_AGE_REACHED = "hard max age reached"
    OWNERSHIP_REACQUIRED = "ownership reacquired"
    RECLAIM_TTL_ELAPSED = "reclaim TTL elapsed"
    CLEANUP_SCHEDULED = "cleanup scheduled"
    CLEANUP_STARTS = "cleanup starts"
    CLEANUP_VERIFIED_COMPLETE = "cleanup verified complete"
    EXTERNAL_ABSENCE_VERIFIED = "external absence verified"


class OwnershipConfidence(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class ReconciliationClassification(str, Enum):
    ACTIVE = "active"
    RECLAIMABLE = "reclaimable"
    TERMINAL_LOST_RUNTIME = "terminal_lost_runtime"
    TERMINAL_AWAITING_CLEANUP = "terminal_awaiting_cleanup"
    CLEANUP_OVERDUE = "cleanup_overdue"
    CLEANED_EXTERNALLY = "cleaned_externally"
    ORPHANED_VERIFIED = "orphaned_verified"
    ORPHANED_UNVERIFIED = "orphaned_unverified"


@dataclass(frozen=True)
class ReconciliationOutcome:
    classification: ReconciliationClassification
    state: SandboxState
    terminal_reason: TerminalReason | None = None


@dataclass(frozen=True)
class _LifecycleTransitionRule:
    to_state: SandboxState
    allowed_reasons: frozenset[TerminalReason]
    cleanup_state: CleanupState | None = None


_NO_REASON: frozenset[TerminalReason] = frozenset()
_TERMINAL_WORKFLOW_REASONS = frozenset(
    {
        TerminalReason.SUCCESS,
        TerminalReason.FAILED,
        TerminalReason.BLOCKED,
        TerminalReason.CANCELED,
        TerminalReason.RESTART_LOOP,
    }
)

_LIFECYCLE_TRANSITIONS: dict[tuple[SandboxState, LifecycleEvent], _LifecycleTransitionRule] = {
    (SandboxState.CREATING, LifecycleEvent.CREATE_ACCEPTED): _LifecycleTransitionRule(
        to_state=SandboxState.STARTING,
        allowed_reasons=_NO_REASON,
    ),
    (SandboxState.CREATING, LifecycleEvent.CREATE_FAILURE): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=frozenset({TerminalReason.CREATE_FAILED}),
    ),
    (SandboxState.STARTING, LifecycleEvent.HEALTH_VERIFIED): _LifecycleTransitionRule(
        to_state=SandboxState.ACTIVE,
        allowed_reasons=_NO_REASON,
    ),
    (SandboxState.STARTING, LifecycleEvent.STARTUP_FAILURE): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=frozenset({TerminalReason.START_FAILED}),
    ),
    (SandboxState.STARTING, LifecycleEvent.LEASE_EXPIRED): _LifecycleTransitionRule(
        to_state=SandboxState.RECLAIMABLE,
        allowed_reasons=frozenset({TerminalReason.LEASE_EXPIRED}),
    ),
    (SandboxState.ACTIVE, LifecycleEvent.RUNTIME_MISSING): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=frozenset({TerminalReason.LOST_RUNTIME}),
    ),
    (SandboxState.ACTIVE, LifecycleEvent.WORKFLOW_TERMINAL_OUTCOME): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=_TERMINAL_WORKFLOW_REASONS,
    ),
    (SandboxState.ACTIVE, LifecycleEvent.LEASE_EXPIRED): _LifecycleTransitionRule(
        to_state=SandboxState.RECLAIMABLE,
        allowed_reasons=frozenset({TerminalReason.LEASE_EXPIRED}),
    ),
    (SandboxState.ACTIVE, LifecycleEvent.HARD_MAX_AGE_REACHED): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=frozenset({TerminalReason.HARD_MAX_AGE}),
    ),
    (SandboxState.RECLAIMABLE, LifecycleEvent.OWNERSHIP_REACQUIRED): _LifecycleTransitionRule(
        to_state=SandboxState.ACTIVE,
        allowed_reasons=_NO_REASON,
    ),
    (SandboxState.RECLAIMABLE, LifecycleEvent.RECLAIM_TTL_ELAPSED): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=frozenset({TerminalReason.LEASE_EXPIRED}),
    ),
    (SandboxState.TERMINAL, LifecycleEvent.CLEANUP_SCHEDULED): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=_NO_REASON,
        cleanup_state=CleanupState.SCHEDULED,
    ),
    (SandboxState.TERMINAL, LifecycleEvent.CLEANUP_STARTS): _LifecycleTransitionRule(
        to_state=SandboxState.TERMINAL,
        allowed_reasons=_NO_REASON,
        cleanup_state=CleanupState.IN_PROGRESS,
    ),
    (SandboxState.TERMINAL, LifecycleEvent.CLEANUP_VERIFIED_COMPLETE): _LifecycleTransitionRule(
        to_state=SandboxState.CLEANED,
        allowed_reasons=_NO_REASON,
        cleanup_state=CleanupState.COMPLETED,
    ),
    (SandboxState.ORPHANED, LifecycleEvent.CLEANUP_VERIFIED_COMPLETE): _LifecycleTransitionRule(
        to_state=SandboxState.CLEANED,
        allowed_reasons=_NO_REASON,
        cleanup_state=CleanupState.COMPLETED,
    ),
    (SandboxState.TERMINAL, LifecycleEvent.EXTERNAL_ABSENCE_VERIFIED): _LifecycleTransitionRule(
        to_state=SandboxState.CLEANED,
        allowed_reasons=frozenset({TerminalReason.CLEANED_EXTERNALLY}),
        cleanup_state=CleanupState.COMPLETED,
    ),
}

_CLEANUP_TRANSITIONS: dict[CleanupState, frozenset[CleanupState]] = {
    CleanupState.NONE: frozenset({CleanupState.NONE, CleanupState.SCHEDULED}),
    CleanupState.SCHEDULED: frozenset({CleanupState.SCHEDULED, CleanupState.IN_PROGRESS, CleanupState.FAILED}),
    CleanupState.IN_PROGRESS: frozenset({CleanupState.IN_PROGRESS, CleanupState.COMPLETED, CleanupState.FAILED}),
    CleanupState.FAILED: frozenset({CleanupState.FAILED, CleanupState.SCHEDULED}),
    CleanupState.COMPLETED: frozenset({CleanupState.COMPLETED}),
}


def validate_lifecycle_transition(
    *,
    current_state: SandboxState,
    event: LifecycleEvent,
    next_state: SandboxState,
    terminal_reason: TerminalReason | None = None,
    cleanup_state: CleanupState | None = None,
) -> bool:
    rule = _LIFECYCLE_TRANSITIONS.get((current_state, event))
    if rule is None:
        raise SandboxLifecycleError(
            f"Illegal lifecycle transition event: {current_state.value} + {event.value}."
        )
    if next_state is not rule.to_state:
        raise SandboxLifecycleError(
            f"Illegal lifecycle destination: {current_state.value} + {event.value} -> {next_state.value}."
        )
    _validate_reason(rule.allowed_reasons, terminal_reason, event)
    if cleanup_state != rule.cleanup_state:
        raise SandboxLifecycleError(
            "Cleanup state does not match lifecycle contract for "
            f"{current_state.value} + {event.value}: expected "
            f"{rule.cleanup_state.value if rule.cleanup_state else 'none'}."
        )
    return True


def validate_cleanup_state_transition(*, current_state: CleanupState, next_state: CleanupState) -> bool:
    allowed = _CLEANUP_TRANSITIONS[current_state]
    if next_state not in allowed:
        raise SandboxLifecycleError(
            f"Illegal cleanup state transition: {current_state.value} -> {next_state.value}."
        )
    return True


def classify_reconciliation(
    *,
    durable_state: SandboxState | None,
    docker_present: bool,
    ownership_confidence: OwnershipConfidence | None = None,
    lease_expired: bool = False,
    cleanup_due_passed: bool = False,
) -> ReconciliationOutcome:
    if durable_state is SandboxState.ACTIVE and docker_present and lease_expired:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.RECLAIMABLE,
            state=SandboxState.RECLAIMABLE,
            terminal_reason=TerminalReason.LEASE_EXPIRED,
        )
    if durable_state is SandboxState.ACTIVE and docker_present:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.ACTIVE,
            state=SandboxState.ACTIVE,
        )
    if durable_state is SandboxState.ACTIVE and not docker_present:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.TERMINAL_LOST_RUNTIME,
            state=SandboxState.TERMINAL,
            terminal_reason=TerminalReason.LOST_RUNTIME,
        )
    if durable_state is SandboxState.TERMINAL and docker_present and cleanup_due_passed:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.CLEANUP_OVERDUE,
            state=SandboxState.TERMINAL,
        )
    if durable_state is SandboxState.TERMINAL and docker_present:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.TERMINAL_AWAITING_CLEANUP,
            state=SandboxState.TERMINAL,
        )
    if durable_state is SandboxState.TERMINAL and not docker_present:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.CLEANED_EXTERNALLY,
            state=SandboxState.CLEANED,
            terminal_reason=TerminalReason.CLEANED_EXTERNALLY,
        )
    if durable_state is None and docker_present and ownership_confidence is OwnershipConfidence.VERIFIED:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.ORPHANED_VERIFIED,
            state=SandboxState.ORPHANED,
            terminal_reason=TerminalReason.ORPHAN_DETECTED,
        )
    if durable_state is None and docker_present and ownership_confidence is OwnershipConfidence.UNVERIFIED:
        return ReconciliationOutcome(
            classification=ReconciliationClassification.ORPHANED_UNVERIFIED,
            state=SandboxState.ORPHANED,
            terminal_reason=TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP,
        )
    raise SandboxLifecycleError(
        "Unsupported reconciliation input combination; add an explicit classification before use."
    )


def assert_lifecycle_fence(
    *,
    expected_owner_instance_id: str,
    actual_owner_instance_id: str,
    expected_lease_epoch: int,
    actual_lease_epoch: int,
    expected_record_version: int,
    actual_record_version: int,
) -> bool:
    if expected_owner_instance_id != actual_owner_instance_id:
        raise SandboxLifecycleError("Stale owner rejected by lifecycle fence.")
    if expected_lease_epoch != actual_lease_epoch:
        raise SandboxLifecycleError("Lease epoch mismatch rejected by lifecycle fence.")
    if expected_record_version != actual_record_version:
        raise SandboxLifecycleError("Record version mismatch rejected by lifecycle fence.")
    return True


def assert_cleanup_claim(
    *,
    current_cleanup_state: CleanupState,
    claimant_id: str,
    existing_cleanup_owner: str | None,
    expected_record_version: int,
    actual_record_version: int,
) -> bool:
    if current_cleanup_state is not CleanupState.SCHEDULED:
        raise SandboxLifecycleError("Cleanup claim requires scheduled cleanup state.")
    if existing_cleanup_owner not in (None, claimant_id):
        raise SandboxLifecycleError("Cleanup claim already owned by another actor.")
    if expected_record_version != actual_record_version:
        raise SandboxLifecycleError("Cleanup claim record version mismatch.")
    return True


def _validate_reason(
    allowed_reasons: frozenset[TerminalReason],
    terminal_reason: TerminalReason | None,
    event: LifecycleEvent,
) -> None:
    if not allowed_reasons and terminal_reason is not None:
        raise SandboxLifecycleError(f"Unexpected terminal reason for event {event.value}.")
    if allowed_reasons and terminal_reason not in allowed_reasons:
        allowed = ", ".join(reason.value for reason in sorted(allowed_reasons, key=lambda item: item.value))
        raise SandboxLifecycleError(
            f"Invalid terminal reason for event {event.value}: "
            f"{terminal_reason.value if terminal_reason else 'none'}. Allowed: {allowed}."
        )
