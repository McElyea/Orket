from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
    resource_id_for_run,
)
from orket.application.workflows.tool_invocation_contracts import build_tool_invocation_manifest
from orket.core.contracts import AttemptRecord, CheckpointRecord, RunRecord, StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    CleanupAuthorityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ExecutionFailureClass,
    FailurePlane,
    LeaseStatus,
    OperatorInputClass,
    OrphanClassification,
    OwnershipClass,
    RecoveryActionClass,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
)
from orket.runtime.run_summary import build_run_summary_payload, write_run_summary_artifact
from tests.application.test_control_plane_publication_service import (
    InMemoryControlPlaneRecordRepository,
)
from tests.application.test_sandbox_control_plane_execution_service import (
    InMemoryControlPlaneExecutionRepository,
)

GENERATED_AT = "2036-03-05T12:00:05+00:00"


async def seed_complete_primary_lineage(
    *,
    tmp_path: Path,
    execution_repo: Any,
    record_repo: Any,
) -> tuple[str, str]:
    session_id = "sess-graph-complete"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    run_root = tmp_path / "runs" / session_id
    run_root.mkdir(parents=True, exist_ok=True)
    publication = ControlPlanePublicationService(repository=record_repo)
    await write_run_summary_artifact(
        root=tmp_path,
        session_id=session_id,
        payload={
            "run_id": run_id,
            "status": "success",
            "duration_ms": 4000,
            "tools_used": ["kernel_action"],
            "artifact_ids": ["control_plane"],
            "failure_reason": None,
        },
    )

    run = RunRecord(
        run_id=run_id,
        workload_id="kernel-action",
        workload_version="1.0",
        policy_snapshot_id="policy-1",
        policy_digest="sha256:policy-1",
        configuration_snapshot_id="config-1",
        configuration_digest="sha256:config-1",
        creation_timestamp="2036-03-05T12:00:00+00:00",
        admission_decision_receipt_ref="admission-1",
        namespace_scope=f"session:{session_id}",
        lifecycle_state=RunState.COMPLETED,
        current_attempt_id=f"{run_id}:attempt:0002",
        final_truth_record_id="truth-1",
    )
    attempt1 = AttemptRecord(
        attempt_id=f"{run_id}:attempt:0001",
        run_id=run_id,
        attempt_ordinal=1,
        attempt_state=AttemptState.INTERRUPTED,
        starting_state_snapshot_ref="snapshot-1",
        start_timestamp="2036-03-05T12:00:00+00:00",
        end_timestamp="2036-03-05T12:00:01+00:00",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        failure_plane=FailurePlane.EXECUTION,
        failure_classification=ExecutionFailureClass.TOOL_TIMEOUT,
        failure_class="tool_timeout",
        recovery_decision_id="rd-1",
    )
    attempt2 = AttemptRecord(
        attempt_id=f"{run_id}:attempt:0002",
        run_id=run_id,
        attempt_ordinal=2,
        attempt_state=AttemptState.COMPLETED,
        starting_state_snapshot_ref="snapshot-2",
        start_timestamp="2036-03-05T12:00:02+00:00",
        end_timestamp="2036-03-05T12:00:04+00:00",
    )
    step1 = StepRecord(
        step_id=f"{run_id}:step:checkpoint",
        attempt_id=attempt1.attempt_id,
        step_kind="governed_kernel_checkpoint",
        namespace_scope=f"session:{session_id}",
        input_ref="receipt:checkpoint-input",
        output_ref="receipt:checkpoint-output",
        capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
        resources_touched=[f"kernel-action-target:{session_id}:trace-1"],
        observed_result_classification="checkpoint_created",
        receipt_refs=["receipt:checkpoint"],
        closure_classification="step_completed",
    )
    step2 = StepRecord(
        step_id=f"{run_id}:step:commit",
        attempt_id=attempt2.attempt_id,
        step_kind="governed_kernel_commit_execution",
        namespace_scope=f"session:{session_id}",
        input_ref="receipt:commit-input",
        output_ref="receipt:commit-output",
        capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
        resources_touched=[f"kernel-action-target:{session_id}:trace-1"],
        observed_result_classification="commit_observed",
        receipt_refs=["receipt:commit"],
        closure_classification="step_completed",
    )

    await execution_repo.save_run_record(record=run)
    await execution_repo.save_attempt_record(record=attempt1)
    await execution_repo.save_attempt_record(record=attempt2)
    await execution_repo.save_step_record(record=step1)
    await execution_repo.save_step_record(record=step2)

    checkpoint = await publication.publish_checkpoint(
        checkpoint=CheckpointRecord(
            checkpoint_id="checkpoint-1",
            parent_ref=attempt1.attempt_id,
            creation_timestamp="2036-03-05T12:00:01+00:00",
            state_snapshot_ref="snapshot-1",
            resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
            invalidation_conditions=["policy_digest_mismatch"],
            dependent_resource_ids=[],
            dependent_effect_refs=[],
            policy_digest="sha256:policy-1",
            integrity_verification_ref="integrity-checkpoint-1",
        )
    )
    await publication.accept_checkpoint(
        acceptance_id="checkpoint-acceptance-1",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2036-03-05T12:00:02+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
    )
    await publication.publish_recovery_decision(
        decision_id="rd-1",
        run_id=run_id,
        failed_attempt_id=attempt1.attempt_id,
        failure_classification_basis="tool_timeout",
        failure_plane=FailurePlane.EXECUTION,
        failure_classification=ExecutionFailureClass.TOOL_TIMEOUT,
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        rationale_ref="recovery-receipt-1",
        target_checkpoint_id=checkpoint.checkpoint_id,
        new_attempt_id=attempt2.attempt_id,
    )
    reservation = await publication.publish_reservation(
        reservation_id=reservation_id_for_run(run_id=run_id),
        holder_ref=f"kernel-action-run:{run_id}",
        reservation_kind=ReservationKind.CONCURRENCY,
        target_scope_ref=f"kernel-action-scope:session:{session_id}",
        creation_timestamp="2036-03-05T12:00:00+00:00",
        expiry_or_invalidation_basis="kernel_action_admission_reserved",
        status=ReservationStatus.ACTIVE,
        supervisor_authority_ref=f"kernel-action-supervisor:{run_id}:admit",
        promotion_rule="promote_on_kernel_action_execution_start",
    )
    lease = await publication.publish_lease(
        lease_id=lease_id_for_run(run_id=run_id),
        resource_id=resource_id_for_run(run=run),
        holder_ref=f"kernel-action-run:{run_id}",
        lease_epoch=1,
        publication_timestamp="2036-03-05T12:00:02+00:00",
        expiry_basis="kernel_action_execution_active",
        status=LeaseStatus.ACTIVE,
        cleanup_eligibility_rule="release_kernel_action_execution_authority_on_terminal_closeout",
        source_reservation_id=reservation.reservation_id,
    )
    await publication.promote_reservation_to_lease(
        reservation_id=reservation.reservation_id,
        promoted_lease_id=lease.lease_id,
        supervisor_authority_ref=f"kernel-action-supervisor:{run_id}:promote",
        promotion_basis="kernel_action_execution_started",
    )
    await publication.publish_resource(
        resource_id=resource_id_for_run(run=run),
        resource_kind="kernel_action_scope",
        namespace_scope=f"session:{session_id}",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state=f"lease_status:{lease.status.value};scope:kernel-action-scope:session:{session_id}",
        last_observed_timestamp="2036-03-05T12:00:02+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref=lease.lease_id,
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )
    await publication.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id=run_id,
        attempt_id=attempt2.attempt_id,
        step_id=step2.step_id,
        authorization_basis_ref="auth-1",
        publication_timestamp="2036-03-05T12:00:03+00:00",
        intended_target_ref=f"kernel-action-scope:session:{session_id}",
        observed_result_ref="receipt:effect-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-effect-1",
    )
    await publication.publish_operator_action(
        action_id="op-1",
        actor_ref="api_key_fingerprint:sha256:test",
        input_class=OperatorInputClass.ATTESTATION,
        target_ref=run_id,
        timestamp="2036-03-05T12:00:04+00:00",
        precondition_basis_ref="receipt:effect-1",
        result="recorded_attestation",
        attestation_scope="run_scope",
        attestation_payload={"operator_verified": True},
        affected_transition_refs=[attempt2.attempt_id],
        affected_resource_refs=[resource_id_for_run(run=run)],
        receipt_refs=["receipt:attestation-1"],
    )
    await publication.publish_final_truth(
        final_truth_record_id="truth-1",
        run_id=run_id,
        result_class=ResultClass.SUCCESS,
        completion_classification=CompletionClassification.SATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
        authoritative_result_ref="receipt:commit-output",
    )
    ledger_summary = build_run_summary_payload(
        run_id=run_id,
        status="success",
        failure_reason=None,
        started_at="2036-03-05T12:00:00+00:00",
        ended_at="2036-03-05T12:00:04+00:00",
        tool_names=["workspace.read", "workspace.write"],
        artifacts={
            "control_plane_run_record": run.model_dump(mode="json"),
            "control_plane_attempt_record": attempt2.model_dump(mode="json"),
            "control_plane_step_record": step2.model_dump(mode="json"),
        },
    )
    events_repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await events_repo.start_run(
        session_id=session_id,
        run_type="kernel-action",
        run_name="Run Evidence Graph",
        department="core",
        build_id="graph-primary-lineage",
    )
    checkpoint_manifest = build_tool_invocation_manifest(
        run_id=session_id,
        tool_name="workspace.read",
        control_plane_run_id=run_id,
        control_plane_attempt_id=attempt1.attempt_id,
        control_plane_step_id=step1.step_id,
        control_plane_resource_id=resource_id_for_run(run=run),
    )
    checkpoint_call = await events_repo.append_event(
        session_id=session_id,
        kind="tool_call",
        payload={
            "operation_id": "op-checkpoint",
            "step_id": "checkpoint:1",
            "tool_name": "workspace.read",
            "tool_args": {"path": "checkpoint.json"},
            "tool_invocation_manifest": checkpoint_manifest,
        },
    )
    await events_repo.append_event(
        session_id=session_id,
        kind="operation_result",
        payload={
            "operation_id": "op-checkpoint",
            "step_id": "checkpoint:1",
            "tool_name": "workspace.read",
            "result": {"ok": True},
            "call_sequence_number": int(checkpoint_call["event_seq"]),
            "tool_call_hash": str(checkpoint_call.get("tool_call_hash") or ""),
            "tool_invocation_manifest": checkpoint_manifest,
        },
    )
    commit_manifest = build_tool_invocation_manifest(
        run_id=session_id,
        tool_name="workspace.write",
        control_plane_run_id=run_id,
        control_plane_attempt_id=attempt2.attempt_id,
        control_plane_step_id=step2.step_id,
        control_plane_resource_id=resource_id_for_run(run=run),
    )
    commit_call = await events_repo.append_event(
        session_id=session_id,
        kind="tool_call",
        payload={
            "operation_id": "op-commit",
            "step_id": "commit:1",
            "tool_name": "workspace.write",
            "tool_args": {"path": "commit.json", "content": "ok"},
            "tool_invocation_manifest": commit_manifest,
        },
    )
    await events_repo.append_event(
        session_id=session_id,
        kind="operation_result",
        payload={
            "operation_id": "op-commit",
            "step_id": "commit:1",
            "tool_name": "workspace.write",
            "result": {"ok": True},
            "call_sequence_number": int(commit_call["event_seq"]),
            "tool_call_hash": str(commit_call.get("tool_call_hash") or ""),
            "tool_invocation_manifest": commit_manifest,
        },
    )
    await events_repo.finalize_run(
        session_id=session_id,
        status="incomplete",
        summary=ledger_summary,
    )
    return session_id, run_id


async def seed_complete_primary_lineage_in_memory(
    *,
    tmp_path: Path,
) -> tuple[
    InMemoryControlPlaneExecutionRepository,
    InMemoryControlPlaneRecordRepository,
    str,
    str,
]:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    session_id, run_id = await seed_complete_primary_lineage(
        tmp_path=tmp_path,
        execution_repo=execution_repo,
        record_repo=record_repo,
    )
    return execution_repo, record_repo, session_id, run_id


async def seed_complete_primary_lineage_sqlite(
    *,
    tmp_path: Path,
) -> tuple[
    AsyncControlPlaneExecutionRepository,
    AsyncControlPlaneRecordRepository,
    Path,
    str,
    str,
]:
    db_path = tmp_path / ".orket" / "durable" / "db" / "control_plane_records.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    execution_repo = AsyncControlPlaneExecutionRepository(db_path)
    record_repo = AsyncControlPlaneRecordRepository(db_path)
    session_id, run_id = await seed_complete_primary_lineage(
        tmp_path=tmp_path,
        execution_repo=execution_repo,
        record_repo=record_repo,
    )
    return execution_repo, record_repo, db_path, session_id, run_id


__all__ = [
    "GENERATED_AT",
    "seed_complete_primary_lineage",
    "seed_complete_primary_lineage_in_memory",
    "seed_complete_primary_lineage_sqlite",
]
