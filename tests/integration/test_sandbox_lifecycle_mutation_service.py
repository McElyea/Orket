# Layer: integration

from __future__ import annotations

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import (
    AsyncSandboxLifecycleRepository,
    SandboxLifecycleConflictError,
)
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxLifecycleError, SandboxState, TerminalReason
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
        "state": SandboxState.TERMINAL,
        "cleanup_state": CleanupState.SCHEDULED,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
        "terminal_reason": "failed",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


@pytest.mark.asyncio
async def test_claim_cleanup_is_idempotent_for_same_operation_id(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record())
    service = SandboxLifecycleMutationService(repo)

    first = await service.claim_cleanup(
        sandbox_id="sb-1",
        operation_id="cleanup-op-1",
        claimant_id="sweeper-a",
        expected_record_version=3,
    )
    second = await service.claim_cleanup(
        sandbox_id="sb-1",
        operation_id="cleanup-op-1",
        claimant_id="sweeper-a",
        expected_record_version=3,
    )

    assert first.reused is False
    assert second.reused is True
    assert second.record.record_version == 4
    assert second.record.cleanup_owner_instance_id == "sweeper-a"


@pytest.mark.asyncio
async def test_claim_cleanup_rejects_stale_version_after_first_claim(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record())
    service = SandboxLifecycleMutationService(repo)

    await service.claim_cleanup(
        sandbox_id="sb-1",
        operation_id="cleanup-op-1",
        claimant_id="sweeper-a",
        expected_record_version=3,
    )

    with pytest.raises(SandboxLifecycleConflictError, match="CAS update rejected"):
        await service.claim_cleanup(
            sandbox_id="sb-1",
            operation_id="cleanup-op-2",
            claimant_id="sweeper-b",
            expected_record_version=3,
        )


@pytest.mark.asyncio
async def test_renew_lease_rejects_stale_owner(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record(state=SandboxState.ACTIVE, cleanup_state=CleanupState.NONE))
    service = SandboxLifecycleMutationService(repo)

    with pytest.raises(SandboxLifecycleError, match="Stale owner"):
        await service.renew_lease(
            sandbox_id="sb-1",
            operation_id="renew-op-1",
            expected_record_version=3,
            expected_owner_instance_id="runner-b",
            expected_lease_epoch=2,
            last_heartbeat_at="2026-03-11T00:01:00+00:00",
            lease_expires_at="2026-03-11T00:06:00+00:00",
        )


@pytest.mark.asyncio
async def test_requires_reconciliation_gate_blocks_follow_on_transition(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(_record())
    service = SandboxLifecycleMutationService(repo)

    flagged = await service.set_requires_reconciliation(
        sandbox_id="sb-1",
        operation_id="flag-op-1",
        expected_record_version=3,
        reason="docker-outcome-unknown",
        requires_reconciliation=True,
    )

    assert flagged.record.requires_reconciliation is True

    with pytest.raises(SandboxLifecycleError, match="requires_reconciliation=true"):
        await service.transition_state(
            sandbox_id="sb-1",
            operation_id="transition-op-1",
            expected_record_version=4,
            event=LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            next_state=SandboxState.CLEANED,
            cleanup_state=CleanupState.COMPLETED,
        )


@pytest.mark.asyncio
async def test_reacquire_ownership_clears_reclaimable_terminal_metadata(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    await repo.save_record(
        _record(
            state=SandboxState.RECLAIMABLE,
            cleanup_state=CleanupState.NONE,
            terminal_reason=TerminalReason.LEASE_EXPIRED,
            cleanup_due_at="2026-03-11T02:00:00+00:00",
        )
    )
    service = SandboxLifecycleMutationService(repo)

    result = await service.reacquire_ownership(
        sandbox_id="sb-1",
        operation_id="reacquire-op-1",
        expected_record_version=3,
        next_owner_instance_id="runner-b",
        next_lease_epoch=3,
        last_heartbeat_at="2026-03-11T00:01:00+00:00",
        lease_expires_at="2026-03-11T00:06:00+00:00",
    )

    assert result.record.state is SandboxState.ACTIVE
    assert result.record.owner_instance_id == "runner-b"
    assert result.record.lease_epoch == 3
    assert result.record.terminal_reason is None
    assert result.record.cleanup_due_at is None
