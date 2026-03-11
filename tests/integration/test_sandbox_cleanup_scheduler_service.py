# Layer: integration

from __future__ import annotations

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.sandbox_cleanup_scheduler_service import SandboxCleanupSchedulerService
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


def _record(sandbox_id: str, *, cleanup_due_at: str, record_version: int, requires_reconciliation: bool = False) -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id=sandbox_id,
        compose_project=f"orket-sandbox-{sandbox_id}",
        workspace_path=f"workspace/{sandbox_id}",
        run_id=f"run-{sandbox_id}",
        owner_instance_id="runner-a",
        lease_epoch=0,
        state=SandboxState.TERMINAL,
        cleanup_state=CleanupState.SCHEDULED,
        record_version=record_version,
        created_at="2026-03-11T00:00:00+00:00",
        terminal_reason=TerminalReason.FAILED,
        cleanup_due_at=cleanup_due_at,
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=requires_reconciliation,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_scheduler_orders_due_candidates_by_due_time_then_sandbox_id(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record("sb-b", cleanup_due_at="2026-03-11T00:10:00+00:00", record_version=2))
    await repo.save_record(_record("sb-a", cleanup_due_at="2026-03-11T00:10:00+00:00", record_version=1))
    await repo.save_record(_record("sb-c", cleanup_due_at="2026-03-11T00:20:00+00:00", record_version=3))
    scheduler = SandboxCleanupSchedulerService(SandboxLifecycleMutationService(repo))

    candidates = await scheduler.list_due_candidates(observed_at="2026-03-11T00:15:00+00:00")

    assert [candidate.sandbox_id for candidate in candidates] == ["sb-a", "sb-b"]


@pytest.mark.asyncio
async def test_scheduler_claims_first_due_candidate_with_cas_safe_mutation(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record("sb-a", cleanup_due_at="2026-03-11T00:10:00+00:00", record_version=1))
    scheduler = SandboxCleanupSchedulerService(SandboxLifecycleMutationService(repo))

    result = await scheduler.claim_next_due_cleanup(
        observed_at="2026-03-11T00:15:00+00:00",
        claimant_id="sweeper-a",
        operation_id_prefix="scheduler-op",
    )

    assert result is not None
    assert result.record.cleanup_state is CleanupState.IN_PROGRESS
    assert result.record.cleanup_owner_instance_id == "sweeper-a"


@pytest.mark.asyncio
async def test_scheduler_skips_reconciliation_blocked_records(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            "sb-a",
            cleanup_due_at="2026-03-11T00:10:00+00:00",
            record_version=1,
            requires_reconciliation=True,
        )
    )
    scheduler = SandboxCleanupSchedulerService(SandboxLifecycleMutationService(repo))

    result = await scheduler.claim_next_due_cleanup(
        observed_at="2026-03-11T00:15:00+00:00",
        claimant_id="sweeper-a",
        operation_id_prefix="scheduler-op",
    )

    assert result is None
