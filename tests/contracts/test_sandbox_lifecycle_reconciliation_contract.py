# Layer: contract

from __future__ import annotations

import pytest

from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_lifecycle_reconciliation_service import (
    SandboxLifecycleReconciliationService,
    SandboxObservation,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, OwnershipConfidence, SandboxState, TerminalReason, validate_lifecycle_transition
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


class _Repo:
    def __init__(self, record: SandboxLifecycleRecord):
        self.record = record

    async def get_record(self, _sandbox_id: str) -> SandboxLifecycleRecord | None:
        return self.record


class _MutationService:
    def __init__(self, record: SandboxLifecycleRecord):
        self.repository = _Repo(record)


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 2,
        "lease_expires_at": "2026-03-11T00:05:00+00:00",
        "state": SandboxState.ACTIVE,
        "cleanup_state": CleanupState.NONE,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


def test_reconciliation_transition_matrix_accepts_runtime_missing_and_external_absence() -> None:
    assert validate_lifecycle_transition(
        current_state=SandboxState.ACTIVE,
        event=LifecycleEvent.RUNTIME_MISSING,
        next_state=SandboxState.TERMINAL,
        terminal_reason=TerminalReason.LOST_RUNTIME,
        cleanup_state=None,
    )
    assert validate_lifecycle_transition(
        current_state=SandboxState.TERMINAL,
        event=LifecycleEvent.EXTERNAL_ABSENCE_VERIFIED,
        next_state=SandboxState.CLEANED,
        terminal_reason=TerminalReason.CLEANED_EXTERNALLY,
        cleanup_state=CleanupState.COMPLETED,
    )


@pytest.mark.parametrize(
    ("state", "reason", "reference_time", "expected"),
    [
        (SandboxState.TERMINAL, TerminalReason.SUCCESS, "2026-03-11T00:00:00+00:00", "2026-03-11T00:15:00+00:00"),
        (SandboxState.TERMINAL, TerminalReason.LOST_RUNTIME, "2026-03-11T00:00:00+00:00", "2026-03-12T00:00:00+00:00"),
        (SandboxState.RECLAIMABLE, TerminalReason.LEASE_EXPIRED, "2026-03-11T00:00:00+00:00", "2026-03-11T02:00:00+00:00"),
        (SandboxState.ORPHANED, TerminalReason.ORPHAN_DETECTED, "2026-03-11T00:00:00+00:00", "2026-03-11T01:00:00+00:00"),
        (SandboxState.ORPHANED, TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP, "2026-03-11T00:00:00+00:00", None),
        (SandboxState.TERMINAL, TerminalReason.HARD_MAX_AGE, "2026-03-11T00:00:00+00:00", "2026-03-11T00:00:00+00:00"),
    ],
)
def test_cleanup_due_policy_maps_required_default_ttls(
    state: SandboxState,
    reason: TerminalReason,
    reference_time: str,
    expected: str | None,
) -> None:
    policy = SandboxLifecyclePolicy()
    assert policy.cleanup_due_at_for(state=state, terminal_reason=reason, reference_time=reference_time) == expected


def test_missing_record_presence_classifies_verified_and_unverified_orphans() -> None:
    service = SandboxLifecycleReconciliationService(mutation_service=_MutationService(_record()))

    verified = service.plan_missing_record_presence(
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:00:00+00:00",
            ownership_confidence=OwnershipConfidence.VERIFIED,
        )
    )
    unverified = service.plan_missing_record_presence(
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:00:00+00:00",
            ownership_confidence=OwnershipConfidence.UNVERIFIED,
        )
    )

    assert verified.terminal_reason is TerminalReason.ORPHAN_DETECTED
    assert verified.cleanup_due_at == "2026-03-11T01:00:00+00:00"
    assert unverified.terminal_reason is TerminalReason.ORPHAN_UNVERIFIED_OWNERSHIP
    assert unverified.cleanup_due_at is None
