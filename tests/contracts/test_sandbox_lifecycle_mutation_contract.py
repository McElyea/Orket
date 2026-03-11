# Layer: contract

from __future__ import annotations

import pytest

from orket.adapters.storage.async_sandbox_lifecycle_repository import SandboxLifecycleConflictError
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxLifecycleError, SandboxState
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


class _FakeRepo:
    def __init__(self, record: SandboxLifecycleRecord):
        self.record = record
        self.operations: dict[str, tuple[str, dict[str, object]]] = {}

    async def get_record(self, sandbox_id: str) -> SandboxLifecycleRecord | None:
        return self.record if self.record.sandbox_id == sandbox_id else None

    async def apply_record_mutation(
        self,
        *,
        operation_id: str,
        payload_hash: str,
        record: SandboxLifecycleRecord,
        expected_record_version: int,
        expected_lease_epoch: int | None = None,
        expected_owner_instance_id: str | None = None,
        expected_cleanup_state: str | None = None,
    ) -> dict[str, object]:
        existing = self.operations.get(operation_id)
        if existing is not None:
            if existing[0] != payload_hash:
                raise SandboxLifecycleError("operation_id reused with different payload hash.")
            return {"reused": True, "result": existing[1]}
        if self.record.record_version != expected_record_version:
            raise SandboxLifecycleConflictError("stale version")
        if expected_cleanup_state is not None and self.record.cleanup_state.value != expected_cleanup_state:
            raise SandboxLifecycleConflictError("stale cleanup state")
        self.record = record
        result = {
            "sandbox_id": record.sandbox_id,
            "record_version": record.record_version,
            "state": record.state.value,
            "cleanup_state": record.cleanup_state.value,
            "requires_reconciliation": record.requires_reconciliation,
        }
        self.operations[operation_id] = (payload_hash, result)
        return {"reused": False, "result": result}


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
async def test_duplicate_operation_id_reuses_prior_cleanup_claim_result() -> None:
    repo = _FakeRepo(_record())
    service = SandboxLifecycleMutationService(repo)

    first = await service.claim_cleanup(
        sandbox_id="sb-1",
        operation_id="op-1",
        claimant_id="sweeper-a",
        expected_record_version=3,
    )
    second = await service.claim_cleanup(
        sandbox_id="sb-1",
        operation_id="op-1",
        claimant_id="sweeper-a",
        expected_record_version=3,
    )

    assert first.reused is False
    assert second.reused is True
    assert second.record.cleanup_owner_instance_id == "sweeper-a"


@pytest.mark.asyncio
async def test_requires_reconciliation_blocks_cleanup_and_state_mutation() -> None:
    repo = _FakeRepo(_record(requires_reconciliation=True))
    service = SandboxLifecycleMutationService(repo)

    with pytest.raises(SandboxLifecycleError, match="requires_reconciliation=true"):
        await service.claim_cleanup(
            sandbox_id="sb-1",
            operation_id="op-1",
            claimant_id="sweeper-a",
            expected_record_version=3,
        )

    with pytest.raises(SandboxLifecycleError, match="requires_reconciliation=true"):
        await service.transition_state(
            sandbox_id="sb-1",
            operation_id="op-2",
            expected_record_version=3,
            event=LifecycleEvent.CLEANUP_VERIFIED_COMPLETE,
            next_state=SandboxState.CLEANED,
            cleanup_state=CleanupState.COMPLETED,
        )
