# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    namespace_resource_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.core.domain import (
    AttemptState,
    CleanupAuthorityClass,
    FailurePlane,
    LeaseStatus,
    OrphanClassification,
    OwnershipClass,
    RecoveryActionClass,
    ReservationStatus,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    TruthFailureClass,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_turn_tool_preflight_terminal_closeout_abandons_non_terminal_attempt() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run = await service._ensure_admission_pending_run(
        session_id="sess-turn-tool-preflight-guard",
        issue_id="ISSUE-PREFLIGHT-GUARD",
        role_name="coder",
        turn_index=1,
        proposal_hash="preflight-guard-proposal-hash",
    )
    assert run.lifecycle_state is RunState.ADMISSION_PENDING
    assert run.current_attempt_id is not None
    assert await execution_repo.get_attempt_record(attempt_id=run.current_attempt_id) is None

    closed_run, truth = await service.publish_preflight_failure(
        session_id="sess-turn-tool-preflight-guard",
        issue_id="ISSUE-PREFLIGHT-GUARD",
        role_name="coder",
        turn_index=1,
        proposal_hash="preflight-guard-proposal-hash",
        violation_reasons=["schema_guard_failed"],
    )
    closed_attempt = await execution_repo.get_attempt_record(attempt_id=str(run.current_attempt_id))
    decision = (
        None
        if closed_attempt is None or closed_attempt.recovery_decision_id is None
        else await record_repo.get_recovery_decision(decision_id=closed_attempt.recovery_decision_id)
    )
    policy_snapshot = await record_repo.get_resolved_policy_snapshot(snapshot_id=closed_run.policy_snapshot_id)
    configuration_snapshot = await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=closed_run.configuration_snapshot_id
    )

    assert closed_run.lifecycle_state is RunState.FAILED_TERMINAL
    assert closed_attempt is not None
    assert closed_attempt.attempt_state is AttemptState.ABANDONED
    assert closed_attempt.end_timestamp is not None
    assert closed_attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert closed_attempt.failure_class == "tool_execution_blocked"
    assert closed_attempt.failure_plane is FailurePlane.TRUTH
    assert closed_attempt.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == closed_run.policy_digest
    assert configuration_snapshot.snapshot_digest == closed_run.configuration_digest
    assert configuration_snapshot.configuration_payload["namespace_scope"] == "issue:ISSUE-PREFLIGHT-GUARD"
    assert truth.result_class is ResultClass.BLOCKED


@pytest.mark.asyncio
async def test_turn_tool_preflight_terminal_closeout_releases_execution_authority_after_promotion() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run, attempt = await service.begin_execution(
        session_id="sess-turn-tool-preflight-promoted",
        issue_id="ISSUE-PREFLIGHT-PROMOTED",
        role_name="coder",
        turn_index=1,
        proposal_hash="preflight-promoted-proposal-hash",
        resume_mode=False,
    )
    assert run.lifecycle_state is RunState.EXECUTING
    assert attempt.attempt_state is AttemptState.EXECUTING

    closed_run, truth = await service.publish_preflight_failure(
        session_id="sess-turn-tool-preflight-promoted",
        issue_id="ISSUE-PREFLIGHT-PROMOTED",
        role_name="coder",
        turn_index=1,
        proposal_hash="preflight-promoted-proposal-hash",
        violation_reasons=["schema_guard_failed"],
    )
    closed_attempt = await execution_repo.get_attempt_record(attempt_id=attempt.attempt_id)
    decision = (
        None
        if closed_attempt is None or closed_attempt.recovery_decision_id is None
        else await record_repo.get_recovery_decision(decision_id=closed_attempt.recovery_decision_id)
    )
    policy_snapshot = await record_repo.get_resolved_policy_snapshot(snapshot_id=closed_run.policy_snapshot_id)
    configuration_snapshot = await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=closed_run.configuration_snapshot_id
    )
    reservation = await record_repo.get_latest_reservation_record(reservation_id=reservation_id_for_run(run_id=run.run_id))
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    resource_history = await record_repo.list_resource_records(resource_id=namespace_resource_id_for_run(run=run))
    latest_resource = await record_repo.get_latest_resource_record(resource_id=namespace_resource_id_for_run(run=run))

    assert closed_run.lifecycle_state is RunState.FAILED_TERMINAL
    assert closed_attempt is not None
    assert closed_attempt.attempt_state is AttemptState.ABANDONED
    assert closed_attempt.end_timestamp is not None
    assert closed_attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert closed_attempt.failure_class == "tool_execution_blocked"
    assert closed_attempt.failure_plane is FailurePlane.TRUTH
    assert closed_attempt.failure_classification is TruthFailureClass.CLAIM_EXCEEDS_AUTHORITY
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == closed_run.policy_digest
    assert configuration_snapshot.snapshot_digest == closed_run.configuration_digest
    assert reservation is not None
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert lease is not None
    assert latest_resource is not None
    assert lease.status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
    assert latest_resource.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert truth.result_class is ResultClass.BLOCKED


@pytest.mark.asyncio
async def test_turn_tool_begin_execution_publishes_durable_snapshots() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run, attempt = await service.begin_execution(
        session_id="sess-turn-tool-snapshot-proof",
        issue_id="ISSUE-SNAPSHOT-PROOF",
        role_name="coder",
        turn_index=1,
        proposal_hash="snapshot-proof-proposal-hash",
        resume_mode=False,
    )
    policy_snapshot = await record_repo.get_resolved_policy_snapshot(snapshot_id=run.policy_snapshot_id)
    configuration_snapshot = await record_repo.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )

    assert run.lifecycle_state is RunState.EXECUTING
    assert run.namespace_scope == "issue:ISSUE-SNAPSHOT-PROOF"
    assert attempt.attempt_state is AttemptState.EXECUTING
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert policy_snapshot.policy_payload["proposal_hash"] == "snapshot-proof-proposal-hash"
    assert configuration_snapshot.snapshot_digest == run.configuration_digest
    assert configuration_snapshot.configuration_payload["namespace_scope"] == "issue:ISSUE-SNAPSHOT-PROOF"


@pytest.mark.asyncio
async def test_turn_tool_begin_execution_fail_closes_reservation_and_lease_on_promotion_error() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run = await service._ensure_admission_pending_run(
        session_id="sess-turn-tool-activation-fail-1",
        issue_id="ISSUE-ACTIVATION-FAIL-1",
        role_name="coder",
        turn_index=1,
        proposal_hash="activation-fail-proposal-hash",
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    service.publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await service.begin_execution(
            session_id="sess-turn-tool-activation-fail-1",
            issue_id="ISSUE-ACTIVATION-FAIL-1",
            role_name="coder",
            turn_index=1,
            proposal_hash="activation-fail-proposal-hash",
            resume_mode=False,
        )

    updated_run = await execution_repo.get_run_record(run_id=run.run_id)
    reservation = await record_repo.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=run.run_id)
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    resource_history = await record_repo.list_resource_records(resource_id=namespace_resource_id_for_run(run=run))

    assert updated_run is not None
    assert updated_run.lifecycle_state is RunState.ADMITTED
    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]


@pytest.mark.asyncio
async def test_turn_tool_begin_execution_fail_closed_on_existing_executing_resource_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run, _attempt = await service.begin_execution(
        session_id="sess-turn-tool-resource-drift-active",
        issue_id="ISSUE-RESOURCE-DRIFT-ACTIVE",
        role_name="coder",
        turn_index=1,
        proposal_hash="resource-drift-active-proposal-hash",
        resume_mode=False,
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    assert lease is not None
    await service.publication.publish_resource(
        resource_id=namespace_resource_id_for_run(run=run),
        resource_kind="turn_tool_namespace",
        namespace_scope="issue:ISSUE-RESOURCE-DRIFT-ACTIVE",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_released;namespace:issue:ISSUE-RESOURCE-DRIFT-ACTIVE",
        last_observed_timestamp="9999-12-31T23:59:59+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref=lease.lease_id,
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    with pytest.raises(ValueError, match="resource state drift"):
        await service.begin_execution(
            session_id="sess-turn-tool-resource-drift-active",
            issue_id="ISSUE-RESOURCE-DRIFT-ACTIVE",
            role_name="coder",
            turn_index=1,
            proposal_hash="resource-drift-active-proposal-hash",
            resume_mode=False,
        )


@pytest.mark.asyncio
async def test_turn_tool_begin_execution_fail_closed_on_completed_reuse_resource_drift() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    service = TurnToolControlPlaneService(
        execution_repository=execution_repo,
        publication=ControlPlanePublicationService(repository=record_repo),
    )

    run, attempt = await service.begin_execution(
        session_id="sess-turn-tool-resource-drift-complete",
        issue_id="ISSUE-RESOURCE-DRIFT-COMPLETE",
        role_name="coder",
        turn_index=1,
        proposal_hash="resource-drift-complete-proposal-hash",
        resume_mode=False,
    )
    completed_run, _completed_attempt, truth = await service.finalize_execution(
        run_id=run.run_id,
        attempt_id=attempt.attempt_id,
        authoritative_result_ref="turn-tool-result:seed-complete",
        violation_reasons=[],
        executed_step_count=1,
    )
    assert truth.result_class is ResultClass.SUCCESS
    await service.publication.publish_resource(
        resource_id=namespace_resource_id_for_run(run=completed_run),
        resource_kind="turn_tool_namespace",
        namespace_scope="issue:ISSUE-RESOURCE-DRIFT-COMPLETE",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_active;namespace:issue:ISSUE-RESOURCE-DRIFT-COMPLETE",
        last_observed_timestamp="9999-12-31T23:59:59+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref="seed_resource_drift_complete",
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    with pytest.raises(ValueError, match="resource state drift"):
        await service.begin_execution(
            session_id="sess-turn-tool-resource-drift-complete",
            issue_id="ISSUE-RESOURCE-DRIFT-COMPLETE",
            role_name="coder",
            turn_index=1,
            proposal_hash="resource-drift-complete-proposal-hash",
            resume_mode=False,
        )
