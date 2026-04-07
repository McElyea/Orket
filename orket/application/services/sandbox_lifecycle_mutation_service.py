from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.core.domain.sandbox_lifecycle import (
    CleanupState,
    LifecycleEvent,
    SandboxLifecycleError,
    SandboxState,
    TerminalReason,
    assert_lifecycle_fence,
    validate_cleanup_state_transition,
    validate_lifecycle_transition,
)
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class SandboxLifecycleMutationResult:
    record: SandboxLifecycleRecord
    reused: bool


class SandboxLifecycleMutationService:
    """Application-layer mutation boundary for sandbox lifecycle authority."""

    def __init__(self, repository: AsyncSandboxLifecycleRepository):
        self.repository = repository

    async def transition_state(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        expected_record_version: int,
        event: LifecycleEvent,
        next_state: SandboxState,
        terminal_reason: TerminalReason | None = None,
        cleanup_state: CleanupState | None = None,
        expected_owner_instance_id: str | None = None,
        expected_lease_epoch: int | None = None,
        next_owner_instance_id: str | None = None,
        next_lease_epoch: int | None = None,
        terminal_at: str | None = None,
        cleanup_due_at: str | None = None,
    ) -> SandboxLifecycleMutationResult:
        current = await self._require_record(sandbox_id)
        self._ensure_not_reconciliation_blocked(current)
        self._assert_fence(
            current=current,
            expected_record_version=expected_record_version,
            expected_owner_instance_id=expected_owner_instance_id,
            expected_lease_epoch=expected_lease_epoch,
        )
        validate_lifecycle_transition(
            current_state=current.state,
            event=event,
            next_state=next_state,
            terminal_reason=terminal_reason,
            cleanup_state=cleanup_state,
        )
        if event is LifecycleEvent.OWNERSHIP_REACQUIRED and (
            next_lease_epoch is None or next_lease_epoch <= current.lease_epoch
        ):
            raise SandboxLifecycleError("Ownership reacquisition requires a strictly newer lease epoch.")
        next_record = current.model_copy(
            update={
                "state": next_state,
                "cleanup_state": cleanup_state or current.cleanup_state,
                "terminal_reason": terminal_reason if terminal_reason is not None else current.terminal_reason,
                "owner_instance_id": next_owner_instance_id
                if next_owner_instance_id is not None
                else current.owner_instance_id,
                "lease_epoch": next_lease_epoch if next_lease_epoch is not None else current.lease_epoch,
                "terminal_at": terminal_at if terminal_at is not None else current.terminal_at,
                "cleanup_due_at": cleanup_due_at if cleanup_due_at is not None else current.cleanup_due_at,
                "record_version": current.record_version + 1,
            }
        )
        payload_hash = self._payload_hash(
            {
                "sandbox_id": sandbox_id,
                "event": event.value,
                "next_state": next_state.value,
                "terminal_reason": terminal_reason.value if terminal_reason else None,
                "cleanup_state": cleanup_state.value if cleanup_state else None,
                "expected_record_version": expected_record_version,
                "expected_owner_instance_id": expected_owner_instance_id,
                "expected_lease_epoch": expected_lease_epoch,
                "next_owner_instance_id": next_owner_instance_id,
                "next_lease_epoch": next_lease_epoch,
                "terminal_at": terminal_at,
                "cleanup_due_at": cleanup_due_at,
            }
        )
        result = await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=payload_hash,
            record=next_record,
            expected_record_version=expected_record_version,
            expected_lease_epoch=expected_lease_epoch,
            expected_owner_instance_id=expected_owner_instance_id,
            expected_cleanup_state=current.cleanup_state.value if cleanup_state is not None else None,
        )
        record = self._mutation_record(result)
        return SandboxLifecycleMutationResult(record=record, reused=bool(result["reused"]))

    async def renew_lease(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        expected_record_version: int,
        expected_owner_instance_id: str,
        expected_lease_epoch: int,
        last_heartbeat_at: str,
        lease_expires_at: str,
    ) -> SandboxLifecycleMutationResult:
        current = await self._require_record(sandbox_id)
        self._assert_fence(
            current=current,
            expected_record_version=expected_record_version,
            expected_owner_instance_id=expected_owner_instance_id,
            expected_lease_epoch=expected_lease_epoch,
        )
        next_record = current.model_copy(
            update={
                "last_heartbeat_at": last_heartbeat_at,
                "lease_expires_at": lease_expires_at,
                "record_version": current.record_version + 1,
            }
        )
        result = await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=self._payload_hash(
                {
                    "sandbox_id": sandbox_id,
                    "expected_record_version": expected_record_version,
                    "expected_owner_instance_id": expected_owner_instance_id,
                    "expected_lease_epoch": expected_lease_epoch,
                    "last_heartbeat_at": last_heartbeat_at,
                    "lease_expires_at": lease_expires_at,
                }
            ),
            record=next_record,
            expected_record_version=expected_record_version,
            expected_lease_epoch=expected_lease_epoch,
            expected_owner_instance_id=expected_owner_instance_id,
        )
        record = self._mutation_record(result)
        return SandboxLifecycleMutationResult(record=record, reused=bool(result["reused"]))

    async def claim_cleanup(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        claimant_id: str,
        expected_record_version: int,
    ) -> SandboxLifecycleMutationResult:
        current = await self._require_record(sandbox_id)
        self._ensure_not_reconciliation_blocked(current)
        if current.state not in {SandboxState.TERMINAL, SandboxState.ORPHANED}:
            raise SandboxLifecycleError("Cleanup claims require terminal or orphaned lifecycle state.")
        validate_cleanup_state_transition(current_state=current.cleanup_state, next_state=CleanupState.IN_PROGRESS)
        next_record = current.model_copy(
            update={
                "cleanup_state": CleanupState.IN_PROGRESS,
                "cleanup_owner_instance_id": claimant_id,
                "record_version": current.record_version + 1,
            }
        )
        result = await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=self._payload_hash(
                {
                    "sandbox_id": sandbox_id,
                    "claimant_id": claimant_id,
                    "expected_record_version": expected_record_version,
                }
            ),
            record=next_record,
            expected_record_version=expected_record_version,
            expected_cleanup_state=current.cleanup_state.value,
        )
        record = self._mutation_record(result)
        return SandboxLifecycleMutationResult(record=record, reused=bool(result["reused"]))

    async def set_requires_reconciliation(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        expected_record_version: int,
        reason: str,
        requires_reconciliation: bool,
    ) -> SandboxLifecycleMutationResult:
        current = await self._require_record(sandbox_id)
        next_record = current.model_copy(
            update={
                "requires_reconciliation": requires_reconciliation,
                "cleanup_failure_reason": reason if requires_reconciliation else current.cleanup_failure_reason,
                "record_version": current.record_version + 1,
            }
        )
        result = await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=self._payload_hash(
                {
                    "sandbox_id": sandbox_id,
                    "expected_record_version": expected_record_version,
                    "requires_reconciliation": requires_reconciliation,
                    "reason": reason,
                }
            ),
            record=next_record,
            expected_record_version=expected_record_version,
        )
        record = self._mutation_record(result)
        return SandboxLifecycleMutationResult(record=record, reused=bool(result["reused"]))

    async def reacquire_ownership(
        self,
        *,
        sandbox_id: str,
        operation_id: str,
        expected_record_version: int,
        next_owner_instance_id: str,
        next_lease_epoch: int,
        last_heartbeat_at: str,
        lease_expires_at: str,
    ) -> SandboxLifecycleMutationResult:
        current = await self._require_record(sandbox_id)
        self._ensure_not_reconciliation_blocked(current)
        self._assert_fence(
            current=current,
            expected_record_version=expected_record_version,
            expected_owner_instance_id=None,
            expected_lease_epoch=None,
        )
        validate_lifecycle_transition(
            current_state=current.state,
            event=LifecycleEvent.OWNERSHIP_REACQUIRED,
            next_state=SandboxState.ACTIVE,
            cleanup_state=None,
        )
        if next_lease_epoch <= current.lease_epoch:
            raise SandboxLifecycleError("Ownership reacquisition requires a strictly newer lease epoch.")
        next_record = current.model_copy(
            update={
                "state": SandboxState.ACTIVE,
                "cleanup_state": CleanupState.NONE,
                "owner_instance_id": next_owner_instance_id,
                "cleanup_owner_instance_id": None,
                "lease_epoch": next_lease_epoch,
                "lease_expires_at": lease_expires_at,
                "last_heartbeat_at": last_heartbeat_at,
                "terminal_reason": None,
                "terminal_at": None,
                "cleanup_due_at": None,
                "cleanup_last_error": None,
                "cleanup_failure_reason": None,
                "required_evidence_ref": None,
                "record_version": current.record_version + 1,
            }
        )
        result = await self.repository.apply_record_mutation(
            operation_id=operation_id,
            payload_hash=self._payload_hash(
                {
                    "sandbox_id": sandbox_id,
                    "expected_record_version": expected_record_version,
                    "next_owner_instance_id": next_owner_instance_id,
                    "next_lease_epoch": next_lease_epoch,
                    "last_heartbeat_at": last_heartbeat_at,
                    "lease_expires_at": lease_expires_at,
                }
            ),
            record=next_record,
            expected_record_version=expected_record_version,
        )
        record = self._mutation_record(result)
        return SandboxLifecycleMutationResult(record=record, reused=bool(result["reused"]))

    async def _require_record(self, sandbox_id: str) -> SandboxLifecycleRecord:
        record = await self.repository.get_record(sandbox_id)
        if record is None:
            raise SandboxLifecycleError(f"Sandbox lifecycle record not found: {sandbox_id}.")
        return record

    @staticmethod
    def _mutation_record(result: dict[str, object]) -> SandboxLifecycleRecord:
        record = result.get("record")
        if not isinstance(record, SandboxLifecycleRecord):
            raise SandboxLifecycleError("Lifecycle mutation repository did not return a written record.")
        return record

    @staticmethod
    def _ensure_not_reconciliation_blocked(record: SandboxLifecycleRecord) -> None:
        if record.requires_reconciliation:
            raise SandboxLifecycleError("Sandbox lifecycle mutation blocked while requires_reconciliation=true.")

    @staticmethod
    def _assert_fence(
        *,
        current: SandboxLifecycleRecord,
        expected_record_version: int,
        expected_owner_instance_id: str | None,
        expected_lease_epoch: int | None,
    ) -> None:
        if expected_owner_instance_id is None or expected_lease_epoch is None:
            if current.record_version != expected_record_version:
                raise SandboxLifecycleError("Record version mismatch rejected by lifecycle fence.")
            return
        assert_lifecycle_fence(
            expected_owner_instance_id=expected_owner_instance_id,
            actual_owner_instance_id=str(current.owner_instance_id or ""),
            expected_lease_epoch=expected_lease_epoch,
            actual_lease_epoch=current.lease_epoch,
            expected_record_version=expected_record_version,
            actual_record_version=current.record_version,
        )

    @staticmethod
    def _payload_hash(payload: dict[str, object]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
