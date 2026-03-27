# Layer: integration

from __future__ import annotations

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.control_plane_workload_catalog import (
    sandbox_runtime_workload_for_tech_stack,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_execution_service import SandboxControlPlaneExecutionService
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_lifecycle_mutation_service import SandboxLifecycleMutationService
from orket.application.services.sandbox_lifecycle_reconciliation_service import (
    SandboxLifecycleReconciliationService,
    SandboxObservation,
)
from orket.application.services.sandbox_lifecycle_view_service import SandboxLifecycleViewService
from orket.core.domain import (
    AttemptState,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    DivergenceClass,
    LeaseStatus,
    ResultClass,
    RunState,
    SafeContinuationClass,
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
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    execution_repo = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    await repo.save_record(_record())
    execution_service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=control_plane_repo),
    )
    await execution_service.initialize_execution(
        sandbox_id="sb-1",
        run_id="run-1",
        workload=sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres"),
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-11T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-1",
        policy=SandboxLifecyclePolicy(),
    )
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo),
        control_plane_publication=ControlPlanePublicationService(repository=control_plane_repo),
        control_plane_execution=execution_service,
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-1",
        observation=SandboxObservation(
            docker_present=False,
            observed_at="2026-03-11T00:10:00+00:00",
        ),
    )

    reconciliation = await control_plane_repo.get_reconciliation_record(
        reconciliation_id="sandbox-reconciliation:run-1:00000004"
    )
    final_truth = await control_plane_repo.get_final_truth(run_id="run-1")
    lease = await control_plane_repo.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    resource = await control_plane_repo.get_latest_resource_record(resource_id="sandbox-scope:sb-1")
    run = await execution_repo.get_run_record(run_id="run-1")
    attempts = await execution_repo.list_attempt_records(run_id="run-1")
    decision = await control_plane_repo.get_recovery_decision(
        decision_id="sandbox-recovery:run-1:terminal:lost_runtime:2026-03-11T00:10:00+00:00"
    )

    assert result is not None
    assert result.record.state is SandboxState.TERMINAL
    assert result.record.terminal_reason is TerminalReason.LOST_RUNTIME
    assert result.record.cleanup_due_at == "2026-03-12T00:10:00+00:00"
    assert reconciliation is not None
    assert lease is not None
    assert lease.status is LeaseStatus.UNCERTAIN
    assert resource is not None
    assert resource.current_observed_state.startswith("sandbox_state:terminal")
    assert resource.orphan_classification.value == "suspected_orphan"
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert run is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id == final_truth.final_truth_record_id
    assert len(attempts) == 1
    assert attempts[0].attempt_state is AttemptState.INTERRUPTED
    assert decision is not None


@pytest.mark.asyncio
async def test_reconciliation_transitions_expired_active_record_to_reclaimable(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    execution_repo = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")
    await repo.save_record(_record())
    execution_service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=control_plane_repo),
    )
    await execution_service.initialize_execution(
        sandbox_id="sb-1",
        run_id="run-1",
        workload=sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres"),
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-11T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-1",
        policy=SandboxLifecyclePolicy(),
    )
    service = SandboxLifecycleReconciliationService(
        mutation_service=SandboxLifecycleMutationService(repo),
        control_plane_publication=ControlPlanePublicationService(repository=control_plane_repo),
        control_plane_execution=execution_service,
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-2",
        observation=SandboxObservation(
            docker_present=True,
            observed_at="2026-03-11T00:10:00+00:00",
        ),
    )

    reconciliation = await control_plane_repo.get_reconciliation_record(
        reconciliation_id="sandbox-reconciliation:run-1:00000004"
    )
    checkpoint = await control_plane_repo.get_checkpoint(
        checkpoint_id="sandbox-checkpoint:sb-1:lease_epoch:00000002"
    )
    checkpoint_acceptance = await control_plane_repo.get_checkpoint_acceptance(
        checkpoint_id="sandbox-checkpoint:sb-1:lease_epoch:00000002"
    )
    snapshot = await repo.get_snapshot("sandbox-lifecycle-snapshot:sb-1:00000004")
    lease = await control_plane_repo.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    resource = await control_plane_repo.get_latest_resource_record(resource_id="sandbox-scope:sb-1")
    run = await execution_repo.get_run_record(run_id="run-1")
    attempts = await execution_repo.list_attempt_records(run_id="run-1")

    assert result is not None
    assert result.record.state is SandboxState.RECLAIMABLE
    assert result.record.terminal_reason is TerminalReason.LEASE_EXPIRED
    assert result.record.cleanup_due_at == "2026-03-11T02:10:00+00:00"
    assert reconciliation is not None
    assert lease is not None
    assert lease.status is LeaseStatus.EXPIRED
    assert resource is not None
    assert resource.current_observed_state.startswith("sandbox_state:reclaimable")
    assert resource.orphan_classification.value == "not_orphaned"
    assert reconciliation.divergence_class is DivergenceClass.OWNERSHIP_DIVERGED
    assert reconciliation.safe_continuation_class is SafeContinuationClass.UNSAFE_TO_CONTINUE
    assert checkpoint is not None
    assert checkpoint.state_snapshot_ref == "sandbox-lifecycle-snapshot:sb-1:00000004"
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert checkpoint.dependent_resource_ids == ["sandbox-scope:sb-1"]
    assert snapshot is not None
    assert snapshot.record.state is SandboxState.RECLAIMABLE
    assert checkpoint_acceptance is not None
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert (
        checkpoint_acceptance.resumability_class
        is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    )
    assert run is not None
    assert run.lifecycle_state is RunState.WAITING_ON_RESOURCE
    assert len(attempts) == 1
    assert attempts[0].attempt_state is AttemptState.INTERRUPTED
    resumed_run, resumed_attempt, recovery_decision = await execution_service.start_new_attempt_after_reacquire(
        sandbox_id="sb-1",
        run_id="run-1",
        lease_epoch=result.record.lease_epoch,
        observed_at="2026-03-11T00:11:00+00:00",
        policy_version="docker_sandbox_lifecycle.v1",
        rationale_ref="sandbox-reconciliation:run-1:00000004",
    )
    assert resumed_run.lifecycle_state is RunState.EXECUTING
    assert resumed_attempt.attempt_state is AttemptState.EXECUTING
    assert recovery_decision is not None
    assert recovery_decision.authorized_next_action.value == "resume_from_checkpoint"
    assert recovery_decision.target_checkpoint_id == checkpoint.checkpoint_id
    assert recovery_decision.new_attempt_id == resumed_attempt.attempt_id
    assert recovery_decision.required_precondition_refs == [
        checkpoint.checkpoint_id,
        checkpoint_acceptance.acceptance_id,
    ]
    resumed_attempts = await execution_repo.list_attempt_records(run_id="run-1")
    assert resumed_attempts[0].recovery_decision_id == recovery_decision.decision_id
    views = await SandboxLifecycleViewService(
        repo,
        control_plane_repository=control_plane_repo,
        control_plane_execution_repository=execution_repo,
    ).list_views(observed_at="2026-03-11T00:11:00+00:00")
    assert views[0].control_plane_recovery_decision_id == recovery_decision.decision_id
    assert views[0].control_plane_recovery_action == "resume_from_checkpoint"
    assert views[0].control_plane_checkpoint_id == checkpoint.checkpoint_id
    assert views[0].control_plane_checkpoint_resumability_class == "resume_new_attempt_from_checkpoint"
    assert views[0].control_plane_reconciliation_id == reconciliation.reconciliation_id
    assert views[0].control_plane_divergence_class == "ownership_diverged"
    assert views[0].control_plane_safe_continuation_class == "unsafe_to_continue"


@pytest.mark.asyncio
async def test_reconciliation_marks_terminal_absent_record_as_cleaned_externally(tmp_path) -> None:
    repo = AsyncSandboxLifecycleRepository(tmp_path / "sandbox_lifecycle.db")
    control_plane_repo = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
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
        mutation_service=SandboxLifecycleMutationService(repo),
        control_plane_publication=ControlPlanePublicationService(repository=control_plane_repo),
    )

    result = await service.reconcile_existing_record(
        sandbox_id="sb-1",
        operation_id="reconcile-op-3",
        observation=SandboxObservation(
            docker_present=False,
            observed_at="2026-03-11T00:30:00+00:00",
        ),
    )

    reconciliation = await control_plane_repo.get_reconciliation_record(
        reconciliation_id="sandbox-reconciliation:run-1:00000004"
    )
    lease = await control_plane_repo.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    resource = await control_plane_repo.get_latest_resource_record(resource_id="sandbox-scope:sb-1")

    assert result is not None
    assert result.record.state is SandboxState.CLEANED
    assert result.record.cleanup_state is CleanupState.COMPLETED
    assert result.record.terminal_reason is TerminalReason.CLEANED_EXTERNALLY
    assert reconciliation is not None
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert resource is not None
    assert resource.current_observed_state.startswith("sandbox_state:cleaned")
    assert resource.orphan_classification.value == "not_orphaned"
    assert reconciliation.divergence_class is DivergenceClass.EXPECTED_EFFECT_OBSERVED
    assert reconciliation.safe_continuation_class is SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP


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
