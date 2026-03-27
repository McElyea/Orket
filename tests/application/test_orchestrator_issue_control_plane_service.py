# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_workload_catalog import (
    ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_service import (
    OrchestratorIssueControlPlaneError,
    OrchestratorIssueControlPlaneService,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    attempt_id_for_run,
    lease_id_for_run,
    reservation_id_for_run,
    run_id_for_dispatch,
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


async def _seed_dispatch_resource_authority(
    *,
    service: OrchestratorIssueControlPlaneService,
    run_id: str,
    session_id: str,
    issue_id: str,
    active_lease: bool,
) -> None:
    reservation = await service.publication.publish_reservation(
        reservation_id=reservation_id_for_run(run_id=run_id),
        holder_ref=f"orchestrator-issue:{session_id}:{issue_id}",
        reservation_kind=ReservationKind.CONCURRENCY,
        target_scope_ref=f"issue-dispatch-slot:{session_id}:{issue_id}",
        creation_timestamp="2026-03-26T16:00:00+00:00",
        expiry_or_invalidation_basis="seed_dispatch_resource_authority",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:seed",
        promotion_rule=service.PROMOTION_RULE,
    )
    lease = await service.publication.publish_lease(
        lease_id=lease_id_for_run(run_id=run_id),
        resource_id=f"issue-dispatch-slot:{session_id}:{issue_id}",
        holder_ref=f"orchestrator-issue:{session_id}:{issue_id}",
        lease_epoch=1,
        publication_timestamp="2026-03-26T16:00:01+00:00",
        expiry_basis="seed_dispatch_resource_authority",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule=service.CLEANUP_RULE,
        source_reservation_id=reservation.reservation_id,
    )
    await service.publication.promote_reservation_to_lease(
        reservation_id=reservation.reservation_id,
        promoted_lease_id=lease.lease_id,
        supervisor_authority_ref=f"orchestrator-issue-supervisor:{run_id}:seed_promote",
        promotion_basis="seed_dispatch_resource_authority",
    )
    await service.publication.publish_resource(
        resource_id=lease.resource_id,
        resource_kind="issue_dispatch_slot",
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
        expiry_basis="seed_dispatch_resource_authority_closed",
        status=LeaseStatus.RELEASED,
        cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
        source_reservation_id=lease.source_reservation_id,
    )
    await service.publication.publish_resource(
        resource_id=released.resource_id,
        resource_kind="issue_dispatch_slot",
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
async def test_orchestrator_issue_dispatch_publishes_durable_snapshots() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    published = await service.publish_issue_transition(
        session_id="sess-issue-1",
        issue_id="ISSUE-1",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )

    run_id = run_id_for_dispatch(
        session_id="sess-issue-1",
        issue_id="ISSUE-1",
        seat_name="coder",
        turn_index=1,
    )
    run = await execution_repo.get_run_record(run_id=run_id)
    policy_snapshot = None if run is None else await record_repo.get_resolved_policy_snapshot(
        snapshot_id=run.policy_snapshot_id
    )
    configuration_snapshot = None if run is None else await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )

    assert published is True
    assert run is not None
    assert run.workload_id == ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD.workload_id
    assert run.workload_version == ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD.workload_version
    assert run.namespace_scope == "issue:ISSUE-1"
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert policy_snapshot.policy_payload == {"reason": "turn_dispatch", "review_turn": False}
    assert configuration_snapshot.snapshot_digest == run.configuration_digest
    assert configuration_snapshot.configuration_payload["seat_name"] == "coder"
    assert configuration_snapshot.configuration_payload["turn_index"] == 1


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_fail_closed_on_promotion_error() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await service.publish_issue_transition(
            session_id="sess-issue-fail-closeout-1",
            issue_id="ISSUE-FAIL-CLOSEOUT-1",
            current_status=CardStatus.READY,
            target_status=CardStatus.IN_PROGRESS,
            reason="turn_dispatch",
            assignee="coder",
            turn_index=1,
            review_turn=False,
        )

    run_id = run_id_for_dispatch(
        session_id="sess-issue-fail-closeout-1",
        issue_id="ISSUE-FAIL-CLOSEOUT-1",
        seat_name="coder",
        turn_index=1,
    )
    run = await execution_repo.get_run_record(run_id=run_id)
    reservation = await record_repo.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=run_id)
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    resource_history = await record_repo.list_resource_records(
        resource_id="issue-dispatch-slot:sess-issue-fail-closeout-1:ISSUE-FAIL-CLOSEOUT-1"
    )

    assert run is not None
    assert run.lifecycle_state is RunState.ADMITTED
    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_blocked_closeout_publishes_terminal_recovery_decision() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    started = await service.publish_issue_transition(
        session_id="sess-issue-recovery-1",
        issue_id="ISSUE-RECOVERY-1",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    closed = await service.publish_issue_transition(
        session_id="sess-issue-recovery-1",
        issue_id="ISSUE-RECOVERY-1",
        current_status=CardStatus.IN_PROGRESS,
        target_status=CardStatus.BLOCKED,
        reason="dependency_blocked",
        assignee=None,
        turn_index=None,
        review_turn=False,
    )

    run_id = run_id_for_dispatch(
        session_id="sess-issue-recovery-1",
        issue_id="ISSUE-RECOVERY-1",
        seat_name="coder",
        turn_index=1,
    )
    run = await execution_repo.get_run_record(run_id=run_id)
    attempt = None if run is None else await execution_repo.get_attempt_record(attempt_id=str(run.current_attempt_id or ""))
    recovery = (
        None
        if attempt is None or attempt.recovery_decision_id is None
        else await record_repo.get_recovery_decision(decision_id=attempt.recovery_decision_id)
    )

    assert started is True
    assert closed is True
    assert run is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id is not None
    assert attempt is not None
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.recovery_decision_id is not None
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert recovery is not None
    assert recovery.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert recovery.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY


@pytest.mark.asyncio
async def test_orchestrator_issue_observed_closeout_publishes_effect_journal_entry() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    started = await service.publish_issue_transition(
        session_id="sess-issue-observe-effect-1",
        issue_id="ISSUE-OBSERVE-EFFECT-1",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    await service.close_from_observed_status(
        session_id="sess-issue-observe-effect-1",
        issue_id="ISSUE-OBSERVE-EFFECT-1",
        observed_status=CardStatus.IN_PROGRESS,
    )

    run_id = run_id_for_dispatch(
        session_id="sess-issue-observe-effect-1",
        issue_id="ISSUE-OBSERVE-EFFECT-1",
        seat_name="coder",
        turn_index=1,
    )
    effects = await record_repo.list_effect_journal_entries(run_id=run_id)
    steps = await execution_repo.list_step_records(attempt_id=f"{run_id}:attempt:0001")
    steps_by_id = {step.step_id.rsplit(":", 1)[-1]: step for step in steps}

    assert started is True
    assert len(effects) == 2
    assert effects[0].step_id == steps_by_id["dispatch"].step_id
    assert effects[-1].step_id == steps_by_id["closeout"].step_id
    assert effects[-1].observed_result_ref is not None


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_fail_closed_when_active_run_exists() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-active",
        issue_id="ISSUE-ACTIVE",
        seat_name="coder",
        turn_index=2,
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.WORKLOAD_ID,
            workload_version=service.WORKLOAD_VERSION,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest="sha256:policy-active",
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest="sha256:config-active",
            creation_timestamp="2026-03-26T16:00:00+00:00",
            admission_decision_receipt_ref="issue-transition:sess-issue-active:ISSUE-ACTIVE:ready->in_progress:turn_dispatch",
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
            starting_state_snapshot_ref="issue-transition:sess-issue-active:ISSUE-ACTIVE:ready->in_progress:turn_dispatch",
            start_timestamp="2026-03-26T16:00:00+00:00",
        )
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="active control-plane truth"):
        await service.publish_issue_transition(
            session_id="sess-issue-active",
            issue_id="ISSUE-ACTIVE",
            current_status=CardStatus.READY,
            target_status=CardStatus.IN_PROGRESS,
            reason="turn_dispatch",
            assignee="coder",
            turn_index=2,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_fail_closed_when_closed_run_attempt_is_non_terminal() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-drift",
        issue_id="ISSUE-DRIFT",
        seat_name="coder",
        turn_index=3,
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.WORKLOAD_ID,
            workload_version=service.WORKLOAD_VERSION,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest="sha256:policy-drift",
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest="sha256:config-drift",
            creation_timestamp="2026-03-26T16:05:00+00:00",
            admission_decision_receipt_ref="issue-transition:sess-issue-drift:ISSUE-DRIFT:ready->in_progress:turn_dispatch",
            namespace_scope="issue:ISSUE-DRIFT",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"orchestrator-issue-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="issue-transition:sess-issue-drift:ISSUE-DRIFT:ready->in_progress:turn_dispatch",
            start_timestamp="2026-03-26T16:05:00+00:00",
        )
    )
    await _seed_dispatch_resource_authority(
        service=service,
        run_id=run_id,
        session_id="sess-issue-drift",
        issue_id="ISSUE-DRIFT",
        active_lease=False,
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="non-terminal attempt"):
        await service.publish_issue_transition(
            session_id="sess-issue-drift",
            issue_id="ISSUE-DRIFT",
            current_status=CardStatus.READY,
            target_status=CardStatus.IN_PROGRESS,
            reason="turn_dispatch",
            assignee="coder",
            turn_index=3,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_fail_closed_when_closed_run_namespace_scope_drifts() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-scope-drift",
        issue_id="ISSUE-SCOPE-DRIFT",
        seat_name="coder",
        turn_index=4,
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.WORKLOAD_ID,
            workload_version=service.WORKLOAD_VERSION,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest="sha256:policy-scope-drift",
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest="sha256:config-scope-drift",
            creation_timestamp="2026-03-26T16:10:00+00:00",
            admission_decision_receipt_ref=(
                "issue-transition:sess-issue-scope-drift:ISSUE-SCOPE-DRIFT:ready->in_progress:turn_dispatch"
            ),
            namespace_scope="issue:DIFFERENT-ISSUE",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"orchestrator-issue-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref=(
                "issue-transition:sess-issue-scope-drift:ISSUE-SCOPE-DRIFT:ready->in_progress:turn_dispatch"
            ),
            start_timestamp="2026-03-26T16:10:00+00:00",
            end_timestamp="2026-03-26T16:10:30+00:00",
        )
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="namespace scope drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-scope-drift",
            issue_id="ISSUE-SCOPE-DRIFT",
            current_status=CardStatus.READY,
            target_status=CardStatus.IN_PROGRESS,
            reason="turn_dispatch",
            assignee="coder",
            turn_index=4,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_dispatch_fail_closed_when_closed_run_has_active_lease_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-lease-drift",
        issue_id="ISSUE-LEASE-DRIFT",
        seat_name="coder",
        turn_index=5,
    )
    attempt_id = attempt_id_for_run(run_id=run_id)
    await execution_repo.save_run_record(
        record=RunRecord(
            run_id=run_id,
            workload_id=service.WORKLOAD_ID,
            workload_version=service.WORKLOAD_VERSION,
            policy_snapshot_id=f"orchestrator-issue-policy:{run_id}",
            policy_digest="sha256:policy-lease-drift",
            configuration_snapshot_id=f"orchestrator-issue-config:{run_id}",
            configuration_digest="sha256:config-lease-drift",
            creation_timestamp="2026-03-26T16:20:00+00:00",
            admission_decision_receipt_ref=(
                "issue-transition:sess-issue-lease-drift:ISSUE-LEASE-DRIFT:ready->in_progress:turn_dispatch"
            ),
            namespace_scope="issue:ISSUE-LEASE-DRIFT",
            lifecycle_state=RunState.COMPLETED,
            current_attempt_id=attempt_id,
            final_truth_record_id=f"orchestrator-issue-final-truth:{run_id}",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref=(
                "issue-transition:sess-issue-lease-drift:ISSUE-LEASE-DRIFT:ready->in_progress:turn_dispatch"
            ),
            start_timestamp="2026-03-26T16:20:00+00:00",
            end_timestamp="2026-03-26T16:20:30+00:00",
        )
    )
    await _seed_dispatch_resource_authority(
        service=service,
        run_id=run_id,
        session_id="sess-issue-lease-drift",
        issue_id="ISSUE-LEASE-DRIFT",
        active_lease=True,
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="active lease drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-lease-drift",
            issue_id="ISSUE-LEASE-DRIFT",
            current_status=CardStatus.READY,
            target_status=CardStatus.IN_PROGRESS,
            reason="turn_dispatch",
            assignee="coder",
            turn_index=5,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_closeout_fail_closed_on_terminal_attempt_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    await service.publish_issue_transition(
        session_id="sess-issue-closeout-drift",
        issue_id="ISSUE-CLOSEOUT-DRIFT",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-closeout-drift",
        issue_id="ISSUE-CLOSEOUT-DRIFT",
        seat_name="coder",
        turn_index=1,
    )
    run = await execution_repo.get_run_record(run_id=run_id)
    assert run is not None
    attempt = await execution_repo.get_attempt_record(attempt_id=str(run.current_attempt_id or ""))
    assert attempt is not None
    await execution_repo.save_attempt_record(record=attempt.model_copy(update={"attempt_state": AttemptState.COMPLETED}))

    with pytest.raises(OrchestratorIssueControlPlaneError, match="terminal attempt drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-closeout-drift",
            issue_id="ISSUE-CLOSEOUT-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            assignee=None,
            turn_index=None,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_closeout_fail_closed_on_non_active_lease_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    await service.publish_issue_transition(
        session_id="sess-issue-closeout-lease-drift",
        issue_id="ISSUE-CLOSEOUT-LEASE-DRIFT",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-closeout-lease-drift",
        issue_id="ISSUE-CLOSEOUT-LEASE-DRIFT",
        seat_name="coder",
        turn_index=1,
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    assert lease is not None
    await service.publication.publish_lease(
        lease_id=lease.lease_id,
        resource_id=lease.resource_id,
        holder_ref=lease.holder_ref,
        lease_epoch=lease.lease_epoch,
        publication_timestamp="9999-12-31T23:59:59+00:00",
        expiry_basis="seed_non_active_lease_drift",
        status=LeaseStatus.RELEASED,
        cleanup_eligibility_rule=lease.cleanup_eligibility_rule,
        source_reservation_id=lease.source_reservation_id,
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="non-active lease drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-closeout-lease-drift",
            issue_id="ISSUE-CLOSEOUT-LEASE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            assignee=None,
            turn_index=None,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_closeout_fail_closed_on_resource_state_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    await service.publish_issue_transition(
        session_id="sess-issue-closeout-resource-drift",
        issue_id="ISSUE-CLOSEOUT-RESOURCE-DRIFT",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-closeout-resource-drift",
        issue_id="ISSUE-CLOSEOUT-RESOURCE-DRIFT",
        seat_name="coder",
        turn_index=1,
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
    assert lease is not None
    await service.publication.publish_resource(
        resource_id=lease.resource_id,
        resource_kind="issue_dispatch_slot",
        namespace_scope="issue:ISSUE-CLOSEOUT-RESOURCE-DRIFT",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_released;namespace:issue:ISSUE-CLOSEOUT-RESOURCE-DRIFT",
        last_observed_timestamp="9999-12-31T23:59:59+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref="seed_resource_state_drift",
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    with pytest.raises(OrchestratorIssueControlPlaneError, match="resource state drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-closeout-resource-drift",
            issue_id="ISSUE-CLOSEOUT-RESOURCE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            assignee=None,
            turn_index=None,
            review_turn=False,
        )


@pytest.mark.asyncio
async def test_orchestrator_issue_closeout_fail_closed_on_namespace_scope_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = OrchestratorIssueControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )
    await service.publish_issue_transition(
        session_id="sess-issue-closeout-scope-drift",
        issue_id="ISSUE-CLOSEOUT-SCOPE-DRIFT",
        current_status=CardStatus.READY,
        target_status=CardStatus.IN_PROGRESS,
        reason="turn_dispatch",
        assignee="coder",
        turn_index=1,
        review_turn=False,
    )
    run_id = run_id_for_dispatch(
        session_id="sess-issue-closeout-scope-drift",
        issue_id="ISSUE-CLOSEOUT-SCOPE-DRIFT",
        seat_name="coder",
        turn_index=1,
    )
    run = await execution_repo.get_run_record(run_id=run_id)
    assert run is not None
    await execution_repo.save_run_record(record=run.model_copy(update={"namespace_scope": "issue:DIFFERENT-ISSUE"}))

    with pytest.raises(OrchestratorIssueControlPlaneError, match="namespace scope drift"):
        await service.publish_issue_transition(
            session_id="sess-issue-closeout-scope-drift",
            issue_id="ISSUE-CLOSEOUT-SCOPE-DRIFT",
            current_status=CardStatus.IN_PROGRESS,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            assignee=None,
            turn_index=None,
            review_turn=False,
        )
