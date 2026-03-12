# Layer: integration

from __future__ import annotations

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.application.services.sandbox_lifecycle_reconciliation_service import (
    SandboxLifecycleReconciliationService,
    SandboxObservation,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


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


@pytest.mark.asyncio
async def test_reconciliation_transitions_active_missing_runtime_to_terminal_lost_runtime(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record())
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo)
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-1",
        observation=SandboxObservation(
            docker_present=False,
            observed_at="2026-03-11T00:10:00+00:00",
        ),
    )

    assert result is not None
    assert result.record.state is SandboxState.TERMINAL
    assert result.record.terminal_reason is TerminalReason.LOST_RUNTIME
    assert result.record.cleanup_due_at == "2026-03-12T00:10:00+00:00"


@pytest.mark.asyncio
async def test_reconciliation_transitions_expired_active_record_to_reclaimable(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record())
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo)
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-2",
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:10:00+00:00",
        ),
    )

    assert result is not None
    assert result.record.state is SandboxState.RECLAIMABLE
    assert result.record.terminal_reason is TerminalReason.LEASE_EXPIRED
    assert result.record.cleanup_due_at == "2026-03-11T02:10:00+00:00"


@pytest.mark.asyncio
async def test_reconciliation_marks_terminal_absent_record_as_cleaned_externally(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.SCHEDULED,
            record_version=3,
            terminal_reason=TerminalReason.FAILED,
            cleanup_due_at="2026-03-11T01:00:00+00:00",
        )
    )
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo)
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-3",
        observation=SandboxObservation(
            docker_present=False,
            observed_at="2026-03-11T00:30:00+00:00",
        ),
    )

    assert result is not None
    assert result.record.state is SandboxState.CLEANED
    assert result.record.cleanup_state is CleanupState.COMPLETED
    assert result.record.terminal_reason is TerminalReason.CLEANED_EXTERNALLY


@pytest.mark.asyncio
async def test_reconciliation_schedules_terminal_cleanup_when_due_is_missing(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.NONE,
            record_version=3,
            terminal_reason=TerminalReason.SUCCESS,
            terminal_at="2026-03-11T00:00:00+00:00",
        )
    )
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo)
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-4",
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:05:00+00:00",
        ),
    )

    assert result is not None
    assert result.record.state is SandboxState.TERMINAL
    assert result.record.cleanup_state is CleanupState.SCHEDULED
    assert result.record.cleanup_due_at == "2026-03-11T00:15:00+00:00"


@pytest.mark.asyncio
async def test_reconciliation_schedules_overdue_terminal_cleanup_when_due_has_passed(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.NONE,
            record_version=3,
            terminal_reason=TerminalReason.SUCCESS,
            terminal_at="2026-03-11T00:00:00+00:00",
            cleanup_due_at="2026-03-11T00:01:00+00:00",
        )
    )
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo)
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-5",
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:05:00+00:00",
        ),
    )

    assert result is not None
    assert result.record.state is SandboxState.TERMINAL
    assert result.record.cleanup_state is CleanupState.SCHEDULED
