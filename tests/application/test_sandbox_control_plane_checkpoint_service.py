# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_checkpoint_service import (
    SandboxControlPlaneCheckpointService,
)
from orket.core.contracts import AttemptRecord, RunRecord
from orket.core.domain import (
    AttemptState,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    RunState,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import (
    ManagedResourceInventory,
    SandboxLifecycleRecord,
    SandboxLifecycleSnapshotRecord,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


class InMemoryLifecycleSnapshotRepository:
    def __init__(self) -> None:
        self.snapshots_by_id: dict[str, SandboxLifecycleSnapshotRecord] = {}

    async def save_snapshot(self, snapshot: SandboxLifecycleSnapshotRecord) -> SandboxLifecycleSnapshotRecord:
        self.snapshots_by_id[snapshot.snapshot_id] = snapshot
        return snapshot


def _reclaimable_record() -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        owner_instance_id="runner-a",
        lease_epoch=2,
        lease_expires_at="2026-03-24T00:05:00+00:00",
        state=SandboxState.RECLAIMABLE,
        cleanup_state=CleanupState.NONE,
        record_version=4,
        created_at="2026-03-24T00:00:00+00:00",
        terminal_reason=TerminalReason.LEASE_EXPIRED,
        cleanup_due_at="2026-03-24T02:00:00+00:00",
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(
            containers=["sb-1-api"],
            networks=["sb-1-net"],
            managed_volumes=["sb-1-db"],
        ),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_checkpoint_service_publishes_checkpoint_backed_new_attempt_reclaimable_checkpoint() -> None:
    record_repo = InMemoryControlPlaneRecordRepository()
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    lifecycle_repo = InMemoryLifecycleSnapshotRepository()
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id="run-1",
            workload_id="sandbox-workload:fastapi-react-postgres",
            workload_version="docker_sandbox_runtime.v1",
            policy_snapshot_id="sandbox-policy:sb-1",
            policy_digest="sha256:policy-1",
            configuration_snapshot_id="sandbox-config:sb-1",
            configuration_digest="sha256:config-1",
            creation_timestamp="2026-03-24T00:00:00+00:00",
            admission_decision_receipt_ref="sandbox-reservation:sb-1",
            lifecycle_state=RunState.WAITING_ON_RESOURCE,
            current_attempt_id="sandbox-attempt:sb-1:00000002",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id="sandbox-attempt:sb-1:00000002",
            run_id="run-1",
            attempt_ordinal=2,
            attempt_state=AttemptState.INTERRUPTED,
            starting_state_snapshot_ref="sandbox-lifecycle:sb-1:active:lease_epoch_2",
            start_timestamp="2026-03-24T00:04:00+00:00",
            end_timestamp="2026-03-24T00:05:00+00:00",
            failure_class="lease_expired",
        )
    )
    checkpoint_service = SandboxControlPlaneCheckpointService(
        publication=publication,
        lifecycle_repository=lifecycle_repo,  # type: ignore[arg-type]
        execution_repository=execution_repo,
    )

    published = await checkpoint_service.publish_reclaimable_checkpoint(
        record=_reclaimable_record(),
        observed_at="2026-03-24T00:05:00+00:00",
    )

    loaded_checkpoint = await record_repo.get_checkpoint(checkpoint_id=published.checkpoint.checkpoint_id)
    loaded_acceptance = await record_repo.get_checkpoint_acceptance(
        checkpoint_id=published.checkpoint.checkpoint_id
    )

    assert published.snapshot.snapshot_id == "sandbox-lifecycle-snapshot:sb-1:00000004"
    assert published.checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert published.acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert loaded_checkpoint is not None
    assert loaded_checkpoint.state_snapshot_ref == published.snapshot.snapshot_id
    assert loaded_acceptance is not None
    assert (
        loaded_acceptance.resumability_class
        is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    )
