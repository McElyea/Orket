from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_lease_service import SandboxControlPlaneLeaseService
from orket.application.services.sandbox_control_plane_reservation_service import SandboxControlPlaneReservationService
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    RunRecord,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    RunState,
)
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import (
    SandboxLifecycleRecord,
    SandboxLifecycleSnapshotRecord,
)


class SandboxControlPlaneCheckpointError(ValueError):
    """Raised when sandbox lifecycle state cannot truthfully publish a checkpoint."""


@dataclass(frozen=True)
class PublishedSandboxCheckpoint:
    checkpoint: CheckpointRecord
    acceptance: CheckpointAcceptanceRecord
    snapshot: SandboxLifecycleSnapshotRecord


class SandboxControlPlaneCheckpointService:
    """Publishes immutable sandbox lifecycle checkpoints for reclaimable runtime state."""

    def __init__(
        self,
        *,
        publication: ControlPlanePublicationService,
        lifecycle_repository: AsyncSandboxLifecycleRepository,
        execution_repository: ControlPlaneExecutionRepository,
    ) -> None:
        self.publication = publication
        self.lifecycle_repository = lifecycle_repository
        self.execution_repository = execution_repository

    async def publish_reclaimable_checkpoint(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> PublishedSandboxCheckpoint:
        run, attempt = await self._require_waiting_execution(record=record)
        snapshot = await self._save_snapshot(record=record, observed_at=observed_at)
        journal_entries = await self.publication.repository.list_effect_journal_entries(run_id=run.run_id)
        checkpoint = await self.publication.publish_checkpoint(
            checkpoint=CheckpointRecord(
                checkpoint_id=self.checkpoint_id_for_record(record),
                parent_ref=attempt.attempt_id,
                creation_timestamp=observed_at,
                state_snapshot_ref=snapshot.snapshot_id,
                resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
                invalidation_conditions=[
                    "policy_digest_mismatch",
                    "lease_state_diverged",
                    "effect_uncertainty_detected",
                    "lifecycle_snapshot_missing",
                ],
                dependent_resource_ids=[f"sandbox-scope:{record.sandbox_id}"],
                dependent_effect_refs=[entry.effect_id for entry in journal_entries],
                policy_digest=run.policy_digest,
                integrity_verification_ref=snapshot.integrity_digest,
            )
        )
        reservation = await self.publication.repository.get_latest_reservation_record(
            reservation_id=SandboxControlPlaneReservationService.reservation_id_for_sandbox(record.sandbox_id)
        )
        acceptance = await self.publication.accept_checkpoint(
            acceptance_id=self.acceptance_id_for_record(record),
            checkpoint=checkpoint,
            supervisor_authority_ref=f"sandbox-reconciliation:{run.run_id}:{record.record_version:08d}",
            decision_timestamp=observed_at,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            integrity_verification_ref=snapshot.integrity_digest,
            journal_entries=journal_entries,
            dependent_effect_entry_refs=[entry.journal_entry_id for entry in journal_entries],
            dependent_reservation_refs=[] if reservation is None else [reservation.reservation_id],
            dependent_lease_refs=[SandboxControlPlaneLeaseService.lease_id_for_sandbox(record.sandbox_id)],
            reservation_ids=[] if reservation is None else [reservation.reservation_id],
            lease_ids=[SandboxControlPlaneLeaseService.lease_id_for_sandbox(record.sandbox_id)],
        )
        return PublishedSandboxCheckpoint(checkpoint=checkpoint, acceptance=acceptance, snapshot=snapshot)

    async def _require_waiting_execution(
        self,
        *,
        record: SandboxLifecycleRecord,
    ) -> tuple[RunRecord, AttemptRecord]:
        if record.state is not SandboxState.RECLAIMABLE or record.terminal_reason is not TerminalReason.LEASE_EXPIRED:
            raise SandboxControlPlaneCheckpointError("reclaimable checkpoint requires lease_expired reclaimable state")
        if record.run_id is None:
            raise SandboxControlPlaneCheckpointError("reclaimable checkpoint requires run_id")
        run = await self.execution_repository.get_run_record(run_id=record.run_id)
        if run is None:
            raise SandboxControlPlaneCheckpointError(f"control-plane run not found for {record.run_id}")
        if run.lifecycle_state is not RunState.WAITING_ON_RESOURCE:
            raise SandboxControlPlaneCheckpointError("reclaimable checkpoint requires waiting_on_resource run state")
        attempt = await self.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id or "")
        if attempt is None:
            raise SandboxControlPlaneCheckpointError("reclaimable checkpoint requires current interrupted attempt")
        return run, attempt

    async def _save_snapshot(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
    ) -> SandboxLifecycleSnapshotRecord:
        payload = record.model_dump(mode="json")
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        snapshot = SandboxLifecycleSnapshotRecord(
            snapshot_id=self.snapshot_id_for_record(record),
            sandbox_id=record.sandbox_id,
            record_version=record.record_version,
            created_at=observed_at,
            integrity_digest=f"sha256:{hashlib.sha256(payload_json.encode('utf-8')).hexdigest()}",
            record=record,
        )
        return await self.lifecycle_repository.save_snapshot(snapshot)

    @staticmethod
    def snapshot_id_for_record(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-lifecycle-snapshot:{record.sandbox_id}:{record.record_version:08d}"

    @staticmethod
    def checkpoint_id_for_record(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-checkpoint:{record.sandbox_id}:lease_epoch:{record.lease_epoch:08d}"

    @staticmethod
    def acceptance_id_for_record(record: SandboxLifecycleRecord) -> str:
        return f"sandbox-checkpoint-acceptance:{record.sandbox_id}:lease_epoch:{record.lease_epoch:08d}"


__all__ = [
    "PublishedSandboxCheckpoint",
    "SandboxControlPlaneCheckpointError",
    "SandboxControlPlaneCheckpointService",
]
