from __future__ import annotations

from dataclasses import dataclass

from orket.adapters.storage.async_sandbox_lifecycle_repository import SandboxLifecycleConflictError
from orket.application.services.sandbox_lifecycle_mutation_service import (
    SandboxLifecycleMutationResult,
    SandboxLifecycleMutationService,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxState
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class CleanupCandidate:
    sandbox_id: str
    cleanup_due_at: str
    record_version: int


class SandboxCleanupSchedulerService:
    """Selects and claims cleanup-eligible sandbox records deterministically."""

    def __init__(self, mutation_service: SandboxLifecycleMutationService):
        self.mutation_service = mutation_service
        self.repository = mutation_service.repository

    async def list_due_candidates(self, *, observed_at: str) -> list[CleanupCandidate]:
        records = await self.repository.list_records()
        candidates = [
            CleanupCandidate(
                sandbox_id=record.sandbox_id,
                cleanup_due_at=str(record.cleanup_due_at),
                record_version=record.record_version,
            )
            for record in records
            if self._is_due_candidate(record=record, observed_at=observed_at)
        ]
        return sorted(candidates, key=lambda item: (item.cleanup_due_at, item.sandbox_id))

    async def claim_next_due_cleanup(
        self,
        *,
        observed_at: str,
        claimant_id: str,
        operation_id_prefix: str,
    ) -> SandboxLifecycleMutationResult | None:
        candidates = await self.list_due_candidates(observed_at=observed_at)
        for candidate in candidates:
            try:
                current = await self.repository.get_record(candidate.sandbox_id)
                if current is None or not self._is_due_candidate(record=current, observed_at=observed_at):
                    continue
                if current.state is SandboxState.TERMINAL and current.cleanup_state in {
                    CleanupState.NONE,
                    CleanupState.FAILED,
                }:
                    current = (
                        await self.mutation_service.transition_state(
                            sandbox_id=current.sandbox_id,
                            operation_id=f"{operation_id_prefix}:schedule:{current.sandbox_id}",
                            expected_record_version=current.record_version,
                            event=LifecycleEvent.CLEANUP_SCHEDULED,
                            next_state=SandboxState.TERMINAL,
                            cleanup_state=CleanupState.SCHEDULED,
                            cleanup_due_at=current.cleanup_due_at or observed_at,
                        )
                    ).record
                return await self.mutation_service.claim_cleanup(
                    sandbox_id=current.sandbox_id,
                    operation_id=f"{operation_id_prefix}:claim:{current.sandbox_id}",
                    claimant_id=claimant_id,
                    expected_record_version=current.record_version,
                )
            except SandboxLifecycleConflictError:
                continue
        return None

    @staticmethod
    def _is_due_candidate(*, record: SandboxLifecycleRecord, observed_at: str) -> bool:
        if record.requires_reconciliation:
            return False
        if record.state not in {SandboxState.TERMINAL, SandboxState.ORPHANED}:
            return False
        if record.cleanup_state is CleanupState.SCHEDULED or record.state is SandboxState.TERMINAL and record.cleanup_state in {
            CleanupState.NONE,
            CleanupState.FAILED,
        }:
            pass
        else:
            return False
        if not record.cleanup_due_at:
            return False
        return str(record.cleanup_due_at) <= observed_at
