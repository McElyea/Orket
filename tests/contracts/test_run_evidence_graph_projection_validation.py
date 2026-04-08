# Layer: contract

from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.runtime.registry.tool_invocation_contracts import build_tool_invocation_manifest
from orket.core.contracts import AttemptRecord, CheckpointRecord, RunRecord
from orket.core.domain import (
    AttemptState,
    CheckpointResumabilityClass,
    ResidualUncertaintyClassification,
    RunState,
    SideEffectBoundaryClass,
)
from orket.runtime.run_evidence_graph_projection import project_run_evidence_graph_primary_lineage
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.contract

_GENERATED_AT = "2036-03-05T12:00:05+00:00"


def _ensure_run_root(tmp_path: Path, session_id: str) -> Path:
    run_root = tmp_path / "runs" / session_id
    run_root.mkdir(parents=True, exist_ok=True)
    return run_root


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_blocks_missing_effect_step_lineage(tmp_path: Path) -> None:
    session_id = "sess-graph-block-effect"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)

    await execution_repo.save_run_record(
        record=RunRecord(
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
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=f"{run_id}:attempt:0001",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=f"{run_id}:attempt:0001",
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
        )
    )
    await publication.append_effect_journal_entry(
        journal_entry_id="journal-orphan-step",
        effect_id="effect-orphan-step",
        run_id=run_id,
        attempt_id=f"{run_id}:attempt:0001",
        step_id=f"{run_id}:step:missing",
        authorization_basis_ref="auth-1",
        publication_timestamp="2036-03-05T12:00:01+00:00",
        intended_target_ref="kernel-action-target",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "blocked"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["issues"][0]["code"] == "effect_step_lineage_missing"


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_accepts_attempt_parent_checkpoints(tmp_path: Path) -> None:
    session_id = "sess-graph-block-checkpoint"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    attempt_id = f"{run_id}:attempt:0001"

    await execution_repo.save_run_record(
        record=RunRecord(
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
            lifecycle_state=RunState.RECOVERY_PENDING,
            current_attempt_id=attempt_id,
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.INTERRUPTED,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
            end_timestamp="2036-03-05T12:00:01+00:00",
            side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        )
    )
    await publication.publish_checkpoint(
        checkpoint=CheckpointRecord(
            checkpoint_id="checkpoint-attempt-parent",
            parent_ref=attempt_id,
            creation_timestamp="2036-03-05T12:00:01+00:00",
            state_snapshot_ref="snapshot-2",
            resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
            invalidation_conditions=["policy_digest_mismatch"],
            dependent_resource_ids=[],
            dependent_effect_refs=[],
            policy_digest="sha256:policy-1",
            integrity_verification_ref="integrity-checkpoint-1",
        )
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "complete"
    assert any(edge["family"] == "attempt_to_checkpoint" for edge in payload["edges"])
    assert not any(edge["family"] == "step_to_checkpoint" for edge in payload["edges"])


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_blocks_terminal_runs_without_final_truth(tmp_path: Path) -> None:
    session_id = "sess-graph-block-final-truth"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()

    await execution_repo.save_run_record(
        record=RunRecord(
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
            current_attempt_id=f"{run_id}:attempt:0001",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=f"{run_id}:attempt:0001",
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.COMPLETED,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
            end_timestamp="2036-03-05T12:00:01+00:00",
        )
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "blocked"
    assert payload["issues"][0]["code"] == "terminal_final_truth_missing"


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_degrades_on_invalid_supplemental_run_summary(
    tmp_path: Path,
) -> None:
    session_id = "sess-graph-degraded-run-summary"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    run_root = _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    (run_root / "run_summary.json").write_text("{\"run_id\":\"wrong-run\"}\n", encoding="utf-8")

    await execution_repo.save_run_record(
        record=RunRecord(
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
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=f"{run_id}:attempt:0001",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=f"{run_id}:attempt:0001",
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
        )
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "degraded"
    assert payload["nodes"]
    assert payload["issues"][0]["code"] == "supplemental_run_summary_invalid"
    assert any(
        summary["source_kind"] == "run_summary.json" and summary["status"] == "contradictory"
        for summary in payload["source_summaries"]
    )


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_degrades_on_runtime_event_alignment_drift(
    tmp_path: Path,
) -> None:
    session_id = "sess-graph-degraded-events"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()

    await execution_repo.save_run_record(
        record=RunRecord(
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
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=f"{run_id}:attempt:0001",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=f"{run_id}:attempt:0001",
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
        )
    )

    events_repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await events_repo.start_run(
        session_id=session_id,
        run_type="kernel-action",
        run_name="Graph Degraded Events",
        department="core",
        build_id="graph-degraded-events",
    )
    manifest = build_tool_invocation_manifest(
        run_id=session_id,
        tool_name="workspace.read",
        control_plane_run_id=run_id,
        control_plane_attempt_id=f"{run_id}:attempt:0001",
        control_plane_step_id=f"{run_id}:step:missing",
    )
    await events_repo.append_event(
        session_id=session_id,
        kind="tool_call",
        payload={
            "operation_id": "op-missing-step",
            "step_id": "missing:1",
            "tool_name": "workspace.read",
            "tool_args": {"path": "missing.txt"},
            "tool_invocation_manifest": manifest,
        },
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "degraded"
    assert payload["nodes"]
    assert payload["issues"][0]["code"] == "supplemental_runtime_event_alignment_invalid"
    assert any(
        summary["source_kind"] == "events.log" and summary["status"] == "contradictory"
        for summary in payload["source_summaries"]
    )


# Layer: contract
@pytest.mark.asyncio
async def test_project_run_evidence_graph_primary_lineage_degrades_on_invalid_run_ledger_summary(
    tmp_path: Path,
) -> None:
    session_id = "sess-graph-degraded-ledger"
    run_id = f"kernel-action-run:{session_id}:trace-1"
    _ensure_run_root(tmp_path, session_id)
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()

    await execution_repo.save_run_record(
        record=RunRecord(
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
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=f"{run_id}:attempt:0001",
        )
    )
    await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id=f"{run_id}:attempt:0001",
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="snapshot-1",
            start_timestamp="2036-03-05T12:00:00+00:00",
        )
    )

    events_repo = AsyncProtocolRunLedgerRepository(tmp_path)
    await events_repo.start_run(
        session_id=session_id,
        run_type="kernel-action",
        run_name="Graph Degraded Ledger",
        department="core",
        build_id="graph-degraded-ledger",
    )
    await events_repo.finalize_run(
        session_id=session_id,
        status="incomplete",
        summary={"run_id": run_id},
    )

    payload = await project_run_evidence_graph_primary_lineage(
        root=tmp_path,
        session_id=session_id,
        run_id=run_id,
        generation_timestamp=_GENERATED_AT,
        execution_repository=execution_repo,
        record_repository=record_repo,
    )

    assert payload["graph_result"] == "degraded"
    assert payload["nodes"]
    assert payload["issues"][0]["code"] == "supplemental_run_ledger_summary_invalid"
    assert any(
        summary["source_kind"] == "run_ledger.summary_json" and summary["status"] == "contradictory"
        for summary in payload["source_summaries"]
    )
