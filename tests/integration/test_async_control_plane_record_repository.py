# Layer: integration

from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
    ControlPlaneRecordConflictError,
)
from orket.adapters.storage.sqlite_connection import current_journal_mode
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import CheckpointRecord, ResolvedConfigurationSnapshot, ResolvedPolicySnapshot
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    CleanupAuthorityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    OperatorCommandClass,
    OperatorInputClass,
    OrphanClassification,
    OwnershipClass,
    RecoveryActionClass,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)

pytestmark = pytest.mark.integration


def _checkpoint() -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-1",
        parent_ref="attempt-1",
        creation_timestamp="2026-03-23T01:20:00+00:00",
        state_snapshot_ref="snapshot-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:sb-1"],
        dependent_effect_refs=["effect-1"],
        policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
    )


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_persists_publication_flow(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)
    checkpoint = _checkpoint()

    reservation = await service.publish_reservation(
        reservation_id="sandbox-reservation:sb-1",
        holder_ref="sandbox-run:run-1",
        reservation_kind=ReservationKind.RESOURCE,
        target_scope_ref="sandbox-allocation:sb-1",
        creation_timestamp="2026-03-23T01:20:30+00:00",
        expiry_or_invalidation_basis="sandbox_create_flow_allocation",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref="sandbox-orchestrator:runner-a:port-allocation",
        promotion_rule="promote_on_lifecycle_record_creation",
    )
    journal_entry = await service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T01:21:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )
    checkpoint_acceptance = await service.accept_checkpoint(
        acceptance_id="accept-1",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T01:22:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
        journal_entries=[journal_entry],
    )
    decision = await service.publish_recovery_decision(
        decision_id="rd-1",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        rationale_ref="recovery-receipt-1",
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
    )
    lease = await service.publish_lease(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:22:15+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:27:15+00:00",
        status=LeaseStatus.ACTIVE,
        last_confirmed_observation="sandbox-lifecycle:sb-1:active:2",
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
        source_reservation_id=reservation.reservation_id,
    )
    promoted_reservation = await service.promote_reservation_to_lease(
        reservation_id=reservation.reservation_id,
        promoted_lease_id=lease.lease_id,
        supervisor_authority_ref="sandbox-lifecycle:sb-1:create_record:runner-a",
        promotion_basis="sandbox_lifecycle_record_created",
    )
    reconciliation = await service.publish_reconciliation(
        reconciliation_id="recon-1",
        target_ref="run-1",
        comparison_scope="run_scope",
        observed_refs=["obs-1"],
        intended_refs=["intent-1"],
        divergence_class=DivergenceClass.RESOURCE_STATE_DIVERGED,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp="2026-03-23T01:22:30+00:00",
        safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
    )
    final_truth = await service.publish_final_truth(
        final_truth_record_id="truth-1",
        run_id="run-1",
        result_class=ResultClass.DEGRADED,
        completion_classification=CompletionClassification.PARTIAL,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        degradation_classification=DegradationClassification.DECLARED,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[
            AuthoritySourceClass.RECONCILIATION_RECORD,
            AuthoritySourceClass.RECEIPT_EVIDENCE,
        ],
    )

    listed_entries = await repository.list_effect_journal_entries(run_id="run-1")
    reservation_history = await repository.list_reservation_records(reservation_id="sandbox-reservation:sb-1")
    loaded_reservation = await repository.get_latest_reservation_record(reservation_id="sandbox-reservation:sb-1")
    loaded_checkpoint = await repository.get_checkpoint(checkpoint_id="checkpoint-1")
    listed_checkpoints = await repository.list_checkpoints(parent_ref="attempt-1")
    loaded_acceptance = await repository.get_checkpoint_acceptance(checkpoint_id="checkpoint-1")
    loaded_decision = await repository.get_recovery_decision(decision_id="rd-1")
    loaded_lease = await repository.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    loaded_reconciliation = await repository.get_reconciliation_record(reconciliation_id="recon-1")
    listed_reconciliations = await repository.list_reconciliation_records(target_ref="run-1")
    latest_reconciliation = await repository.get_latest_reconciliation_record(target_ref="run-1")
    loaded_truth = await repository.get_final_truth(run_id="run-1")
    holder_reservations = await repository.list_reservation_records_for_holder_ref(holder_ref="sandbox-run:run-1")
    latest_holder_reservation = await repository.get_latest_reservation_record_for_holder_ref(
        holder_ref="sandbox-run:run-1"
    )

    assert [entry.journal_entry_id for entry in listed_entries] == ["journal-1"]
    assert [record.status for record in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert promoted_reservation.promoted_lease_id == loaded_reservation.promoted_lease_id
    assert checkpoint.checkpoint_id == loaded_checkpoint.checkpoint_id
    assert listed_checkpoints == [checkpoint]
    assert checkpoint_acceptance.acceptance_id == loaded_acceptance.acceptance_id
    assert decision.decision_id == loaded_decision.decision_id
    assert lease.publication_timestamp == loaded_lease.publication_timestamp
    assert reconciliation.reconciliation_id == loaded_reconciliation.reconciliation_id
    assert listed_reconciliations == [reconciliation]
    assert latest_reconciliation is not None
    assert latest_reconciliation.reconciliation_id == reconciliation.reconciliation_id
    assert [record.reservation_id for record in holder_reservations] == ["sandbox-reservation:sb-1", "sandbox-reservation:sb-1"]
    assert latest_holder_reservation is not None
    assert latest_holder_reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert final_truth.final_truth_record_id == loaded_truth.final_truth_record_id


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_enables_wal_mode(tmp_path: Path) -> None:
    """Layer: integration. Verifies control-plane record storage selects WAL mode on the real SQLite file."""
    db_path = tmp_path / "control_plane.sqlite3"
    repository = AsyncControlPlaneRecordRepository(db_path)

    await repository.save_resolved_policy_snapshot(
        snapshot=ResolvedPolicySnapshot(
            snapshot_id="policy-wal",
            snapshot_digest="sha256:policy-wal",
            created_at="2026-04-25T00:00:00+00:00",
            source_refs=["test"],
            policy_payload={"mode": "test"},
        )
    )

    assert await current_journal_mode(db_path) == "wal"


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_persists_operator_action_flow(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)

    action = await service.publish_operator_action(
        action_id="op-1",
        actor_ref="api_key_fingerprint:sha256:test",
        input_class=OperatorInputClass.COMMAND,
        target_ref="run-1",
        timestamp="2026-03-24T01:10:00+00:00",
        precondition_basis_ref="sandbox-lifecycle:sb-1:active:3",
        result="accepted",
        command_class=OperatorCommandClass.CANCEL_RUN,
        affected_transition_refs=["sandbox-lifecycle:sb-1:active->cleaned:7"],
        affected_resource_refs=["sandbox-runtime:sb-1"],
        receipt_refs=["truth-1"],
    )

    loaded = await repository.get_operator_action(action_id="op-1")
    listed = await repository.list_operator_actions(target_ref="run-1")

    assert loaded is not None
    assert loaded.action_id == action.action_id
    assert listed == [action]


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_persists_resource_history(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)

    first = await service.publish_resource(
        resource_id="sandbox-scope:sb-1",
        resource_kind="sandbox_runtime",
        namespace_scope="sandbox-scope:sb-1",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="sandbox_state:creating;cleanup_state:none;lease_epoch:1;terminal_reason:none;reconciliation_not_required",
        last_observed_timestamp="2026-03-24T01:00:00+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION,
        provenance_ref="sandbox-lifecycle:sb-1:creating:1",
        reconciliation_status="reconciliation_not_required",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )
    second = await service.publish_resource(
        resource_id="sandbox-scope:sb-1",
        resource_kind="sandbox_runtime",
        namespace_scope="sandbox-scope:sb-1",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="sandbox_state:active;cleanup_state:none;lease_epoch:1;terminal_reason:none;reconciliation_not_required",
        last_observed_timestamp="2026-03-24T01:01:00+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION,
        provenance_ref="sandbox-lifecycle:sb-1:active:2",
        reconciliation_status="reconciliation_not_required",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    history = await repository.list_resource_records(resource_id="sandbox-scope:sb-1")
    latest = await repository.get_latest_resource_record(resource_id="sandbox-scope:sb-1")

    assert history == [first, second]
    assert latest is not None
    assert latest.current_observed_state.startswith("sandbox_state:active")
    assert latest.provenance_ref == "sandbox-lifecycle:sb-1:active:2"


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_rejects_conflicting_record_id_reuse(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)

    await service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T01:23:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )

    with pytest.raises(ControlPlaneRecordConflictError, match="reused with different payload"):
        await service.append_effect_journal_entry(
            journal_entry_id="journal-1",
            effect_id="effect-2",
            run_id="run-1",
            attempt_id="attempt-1",
            step_id="step-2",
            authorization_basis_ref="auth-2",
            publication_timestamp="2026-03-23T01:24:00+00:00",
            intended_target_ref="resource:sb-2",
            observed_result_ref="receipt-2",
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref="integrity-2",
        )


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_persists_resolved_snapshots(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    policy_snapshot = ResolvedPolicySnapshot(
        snapshot_id="policy-1",
        snapshot_digest="sha256:policy-1",
        created_at="2026-03-25T01:00:00+00:00",
        source_refs=["admission-ref-1"],
        policy_payload={"mode": "strict"},
    )
    configuration_snapshot = ResolvedConfigurationSnapshot(
        snapshot_id="config-1",
        snapshot_digest="sha256:config-1",
        created_at="2026-03-25T01:00:00+00:00",
        source_refs=["admission-ref-1"],
        configuration_payload={"session_id": "sess-1"},
    )

    await repository.save_resolved_policy_snapshot(snapshot=policy_snapshot)
    await repository.save_resolved_configuration_snapshot(snapshot=configuration_snapshot)

    loaded_policy = await repository.get_resolved_policy_snapshot(snapshot_id=policy_snapshot.snapshot_id)
    loaded_configuration = await repository.get_resolved_configuration_snapshot(
        snapshot_id=configuration_snapshot.snapshot_id
    )

    assert loaded_policy == policy_snapshot
    assert loaded_configuration == configuration_snapshot
