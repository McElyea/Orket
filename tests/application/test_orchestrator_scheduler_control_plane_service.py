# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_workload_catalog import (
    ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD,
    ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    attempt_id_for_run,
    lease_id_for_run,
    scheduler_run_id_for_transition,
)
from orket.application.services.orchestrator_scheduler_control_plane_service import (
    OrchestratorSchedulerControlPlaneError,
    OrchestratorSchedulerControlPlaneService,
)
from orket.core.contracts import AttemptRecord, RunRecord
from orket.core.domain import (
    AttemptState,
    CleanupAuthorityClass,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
    RecoveryActionClass,
    ReservationKind,
    ReservationStatus,
    RunState,
    SideEffectBoundaryClass,
    TruthFailureClass,
)
from orket.schema import CardStatus
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


async def _seed_scheduler_resource_authority(
    *,
    service: OrchestratorSchedulerControlPlaneService,
    run_id: str,
    issue_id: str,
    active_lease: bool,
) -> None:
    workload_id = service.TRANSITION_WORKLOAD.workload_id
    reservation = await service.publication.publish_reservation(
        reservation_id=f"{workload_id}-reservation:{run_id}",
        holder_ref=f"orchestrator-issue-scheduler:sess:{issue_id}",
        reservation_kind=ReservationKind.NAMESPACE,
        target_scope_ref=f"namespace:issue:{issue_id}",
        creation_timestamp="2026-03-26T16:00:00+00:00",
        expiry_or_invalidation_basis="seed_scheduler_resource_authority",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"{workload_id}-supervisor:{run_id}:seed",
        promotion_rule=service.PROMOTION_RULE,
    )
    lease = await service.publication.publish_lease(
        lease_id=lease_id_for_run(run_id=run_id),
        resource_id=f"namespace:issue:{issue_id}",
        holder_ref=f"orchestrator-issue-scheduler:sess:{issue_id}",
        lease_epoch=1,
        publication_timestamp="2026-03-26T16:00:01+00:00",
        expiry_basis="seed_scheduler_resource_authority",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule=service.CLEANUP_RULE,
        source_reservation_id=reservation.reservation_id,
    )
    await service.publication.promote_reservation_to_lease(
        reservation_id=reservation.reservation_id,
        promoted_lease_id=lease.lease_id,
        supervisor_authority_ref=f"{workload_id}-supervisor:{run_id}:seed_promote",
        promotion_basis="seed_scheduler_resource_authority",
    )
    await service.publication.publish_resource(
        resource_id=lease.resource_id,
        resource_kind="scheduler_namespace",
        namespace_scope=f"issue:{issue_id}",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state=f"lease_status:{lease.status.value};namespace:issue:{issue_id}",
        last_observed_timestamp=lease.publication_timestamp,
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref=lease.lease_id,
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )
    if active_lease:
        return
    released = await service.publication.publish_lease(
        lease_id=lease.lease_id,
        resource_id=lease.resource_id,
        holder_ref=lease.holder_ref,
        lease_epoch=lease.lease_epoch,
        publication_timestamp="2026-03-26T16:00:02+00:00",
        expiry_basis="seed_scheduler_resource_authority_closed",
        status=LeaseStatus.RELEASED,
        cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
        source_reservation_id=lease.source_reservation_id,
    )
    await service.publication.publish_resource(
        resource_id=released.resource_id,
        resource_kind="scheduler_namespace",
        namespace_scope=f"issue:{issue_id}",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state=f"lease_status:{released.status.value};namespace:issue:{issue_id}",
        last_observed_timestamp=released.publication_timestamp,
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref=released.lease_id,
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_publishes_durable_snapshots() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run_id = await service.publish_scheduler_transition(
        session_id="sess-scheduler-1",
        issue_id="ISSUE-2",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.BLOCKED,
        reason="dependency_blocked",
        metadata={"dependency_issue_id": "ISSUE-1"},
    )

    expected_run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-1",
        issue_id="ISSUE-2",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.BLOCKED,
        reason="dependency_blocked",
        metadata={"dependency_issue_id": "ISSUE-1"},
    )
    run = None if run_id is None else await execution_repo.get_run_record(run_id=run_id)
    attempt = None if run is None else await execution_repo.get_attempt_record(attempt_id=str(run.current_attempt_id or ""))
    policy_snapshot = None if run is None else await record_repo.get_resolved_policy_snapshot(
        snapshot_id=run.policy_snapshot_id
    )
    configuration_snapshot = None if run is None else await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )
    recovery = None
    if attempt is not None and attempt.recovery_decision_id is not None:
        recovery = await record_repo.get_recovery_decision(decision_id=attempt.recovery_decision_id)

    assert run_id == expected_run_id
    assert run is not None
    assert run.workload_id == ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_id
    assert run.workload_version == ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_version
    assert attempt is not None
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.recovery_decision_id is not None
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert run.final_truth_record_id is not None
    assert recovery is not None
    assert recovery.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert recovery.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert recovery.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert policy_snapshot.policy_payload["reason"] == "dependency_blocked"
    assert configuration_snapshot.snapshot_digest == run.configuration_digest
    assert configuration_snapshot.configuration_payload["current_status"] == CardStatus.IN_PROGRESS.value
    assert configuration_snapshot.configuration_payload["target_status"] == CardStatus.BLOCKED.value


@pytest.mark.asyncio
async def test_orchestrator_child_issue_creation_publishes_durable_snapshots() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run_id = await service.publish_child_issue_creation(
        session_id="sess-scheduler-2",
        issue_id="ISSUE-3",
        active_build="build-17",
        seat_name="coder",
        relationship_class="replan_child",
        trigger_issue_ids=["ISSUE-1", "ISSUE-2"],
        metadata={"source": "team_replan"},
    )

    run = None if run_id is None else await execution_repo.get_run_record(run_id=run_id)
    policy_snapshot = None if run is None else await record_repo.get_resolved_policy_snapshot(
        snapshot_id=run.policy_snapshot_id
    )
    configuration_snapshot = None if run is None else await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )

    assert run_id is not None
    assert run is not None
    assert run.workload_id == ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD.workload_id
    assert run.workload_version == ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD.workload_version
    assert run.final_truth_record_id is not None
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert policy_snapshot.policy_payload["relationship_class"] == "replan_child"
    assert configuration_snapshot.snapshot_digest == run.configuration_digest
    assert configuration_snapshot.configuration_payload["active_build"] == "build-17"
    assert configuration_snapshot.configuration_payload["trigger_issue_ids"] == ["ISSUE-1", "ISSUE-2"]


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_fail_closed_when_active_run_exists() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-active",
        issue_id="ISSUE-ACTIVE",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.READY,
        reason="retry_scheduled",
        metadata={"retry_count": 1},
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.TRANSITION_WORKLOAD.workload_id,
            workload_version=service.TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-policy:{run_id}",
            policy_digest="sha256:policy-active",
            configuration_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-config:{run_id}",
            configuration_digest="sha256:config-active",
            creation_timestamp="2026-03-26T14:00:00+00:00",
            admission_decision_receipt_ref="issue-transition:sess-scheduler-active:ISSUE-ACTIVE:in_progress->ready:retry_scheduled",
            namespace_scope="issue:ISSUE-ACTIVE",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=attempt_id,
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="issue-transition:sess-scheduler-active:ISSUE-ACTIVE:in_progress->ready:retry_scheduled",
            start_timestamp="2026-03-26T14:00:00+00:00",
        )
    )

    with pytest.raises(OrchestratorSchedulerControlPlaneError, match="active control-plane truth"):
        await service.publish_scheduler_transition(
            session_id="sess-scheduler-active",
            issue_id="ISSUE-ACTIVE",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.READY,
            reason="retry_scheduled",
            metadata={"retry_count": 1},
        )


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_fail_closed_when_closed_run_attempt_is_non_terminal() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-drift",
        issue_id="ISSUE-DRIFT",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.BLOCKED,
        reason="dependency_blocked",
        metadata={"dependency_issue_id": "ISSUE-X"},
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.TRANSITION_WORKLOAD.workload_id,
            workload_version=service.TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-policy:{run_id}",
            policy_digest="sha256:policy-drift",
            configuration_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-config:{run_id}",
            configuration_digest="sha256:config-drift",
            creation_timestamp="2026-03-26T14:05:00+00:00",
            admission_decision_receipt_ref="issue-transition:sess-scheduler-drift:ISSUE-DRIFT:in_progress->blocked:dependency_blocked",
            namespace_scope="issue:ISSUE-DRIFT",
            lifecycle_state=RunState.FAILED_TERMINAL,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"{service.TRANSITION_WORKLOAD.workload_id}-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="issue-transition:sess-scheduler-drift:ISSUE-DRIFT:in_progress->blocked:dependency_blocked",
            start_timestamp="2026-03-26T14:05:00+00:00",
        )
    )
    await _seed_scheduler_resource_authority(
        service=service,
        run_id=run_id,
        issue_id="ISSUE-DRIFT",
        active_lease=False,
    )

    with pytest.raises(OrchestratorSchedulerControlPlaneError, match="non-terminal attempt"):
        await service.publish_scheduler_transition(
            session_id="sess-scheduler-drift",
            issue_id="ISSUE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            metadata={"dependency_issue_id": "ISSUE-X"},
        )


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_fail_closed_when_closed_run_namespace_scope_drifts() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-scope-drift",
        issue_id="ISSUE-SCOPE-DRIFT",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.READY,
        reason="retry_scheduled",
        metadata={"retry_count": 2},
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.TRANSITION_WORKLOAD.workload_id,
            workload_version=service.TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-policy:{run_id}",
            policy_digest="sha256:policy-scope-drift",
            configuration_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-config:{run_id}",
            configuration_digest="sha256:config-scope-drift",
            creation_timestamp="2026-03-26T16:15:00+00:00",
            admission_decision_receipt_ref=(
                "issue-transition:sess-scheduler-scope-drift:ISSUE-SCOPE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            namespace_scope="issue:DIFFERENT-ISSUE",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"{service.TRANSITION_WORKLOAD.workload_id}-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref=(
                "issue-transition:sess-scheduler-scope-drift:ISSUE-SCOPE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            start_timestamp="2026-03-26T16:15:00+00:00",
            end_timestamp="2026-03-26T16:15:30+00:00",
        )
    )
    await _seed_scheduler_resource_authority(
        service=service,
        run_id=run_id,
        issue_id="ISSUE-SCOPE-DRIFT",
        active_lease=False,
    )

    with pytest.raises(OrchestratorSchedulerControlPlaneError, match="namespace scope drift"):
        await service.publish_scheduler_transition(
            session_id="sess-scheduler-scope-drift",
            issue_id="ISSUE-SCOPE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.READY,
            reason="retry_scheduled",
            metadata={"retry_count": 2},
        )


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_fail_closed_when_closed_run_has_active_lease_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-lease-drift",
        issue_id="ISSUE-LEASE-DRIFT",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.READY,
        reason="retry_scheduled",
        metadata={"retry_count": 3},
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.TRANSITION_WORKLOAD.workload_id,
            workload_version=service.TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-policy:{run_id}",
            policy_digest="sha256:policy-lease-drift",
            configuration_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-config:{run_id}",
            configuration_digest="sha256:config-lease-drift",
            creation_timestamp="2026-03-26T16:25:00+00:00",
            admission_decision_receipt_ref=(
                "issue-transition:sess-scheduler-lease-drift:ISSUE-LEASE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            namespace_scope="issue:ISSUE-LEASE-DRIFT",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"{service.TRANSITION_WORKLOAD.workload_id}-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref=(
                "issue-transition:sess-scheduler-lease-drift:ISSUE-LEASE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            start_timestamp="2026-03-26T16:25:00+00:00",
            end_timestamp="2026-03-26T16:25:30+00:00",
        )
    )
    await _seed_scheduler_resource_authority(
        service=service,
        run_id=run_id,
        issue_id="ISSUE-LEASE-DRIFT",
        active_lease=True,
    )

    with pytest.raises(OrchestratorSchedulerControlPlaneError, match="active lease drift"):
        await service.publish_scheduler_transition(
            session_id="sess-scheduler-lease-drift",
            issue_id="ISSUE-LEASE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.READY,
            reason="retry_scheduled",
            metadata={"retry_count": 3},
        )


@pytest.mark.asyncio
async def test_orchestrator_scheduler_transition_fail_closed_when_closed_run_resource_state_drifts() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorSchedulerControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = scheduler_run_id_for_transition(
        session_id="sess-scheduler-resource-drift",
        issue_id="ISSUE-RESOURCE-DRIFT",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.READY,
        reason="retry_scheduled",
        metadata={"retry_count": 4},
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.TRANSITION_WORKLOAD.workload_id,
            workload_version=service.TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-policy:{run_id}",
            policy_digest="sha256:policy-resource-drift",
            configuration_snapshot_id=f"{service.TRANSITION_WORKLOAD.workload_id}-config:{run_id}",
            configuration_digest="sha256:config-resource-drift",
            creation_timestamp="2026-03-26T16:30:00+00:00",
            admission_decision_receipt_ref=(
                "issue-transition:sess-scheduler-resource-drift:ISSUE-RESOURCE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            namespace_scope="issue:ISSUE-RESOURCE-DRIFT",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"{service.TRANSITION_WORKLOAD.workload_id}-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref=(
                "issue-transition:sess-scheduler-resource-drift:ISSUE-RESOURCE-DRIFT:in_progress->ready:retry_scheduled"
            ),
            start_timestamp="2026-03-26T16:30:00+00:00",
            end_timestamp="2026-03-26T16:30:30+00:00",
        )
    )
    await _seed_scheduler_resource_authority(
        service=service,
        run_id=run_id,
        issue_id="ISSUE-RESOURCE-DRIFT",
        active_lease=False,
    )
    await service.publication.publish_resource(
        resource_id="namespace:issue:ISSUE-RESOURCE-DRIFT",
        resource_kind="scheduler_namespace",
        namespace_scope="issue:ISSUE-RESOURCE-DRIFT",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_active;namespace:issue:ISSUE-RESOURCE-DRIFT",
        last_observed_timestamp="9999-12-31T23:59:59+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref="seed_resource_state_drift",
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    with pytest.raises(OrchestratorSchedulerControlPlaneError, match="resource state drift"):
        await service.publish_scheduler_transition(
            session_id="sess-scheduler-resource-drift",
            issue_id="ISSUE-RESOURCE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.READY,
            reason="retry_scheduled",
            metadata={"retry_count": 4},
        )
