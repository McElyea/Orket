# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.contracts.control_plane_models import AttemptRecord, CheckpointRecord, RunRecord, StepRecord
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
    OrphanClassification,
    OwnershipClass,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)
from orket.orchestration.engine import OrchestrationEngine
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


class _FakePendingGates:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.rows = list(rows or [_tool_approval_row()])

    async def list_requests(self, *, session_id=None, status=None, limit=100):
        rows = list(self.rows)
        if session_id:
            rows = [row for row in rows if row["session_id"] == session_id]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return rows[: max(1, int(limit))]

    async def resolve_request(self, *, request_id: str, status: str, resolution=None) -> None:
        for row in self.rows:
            if row["request_id"] == request_id:
                row["status"] = status
                row["resolution_json"] = dict(resolution or {})
                row["resolved_at"] = "2026-03-03T12:01:00+00:00"
                return
        raise RuntimeError("request not found")


def _tool_approval_row(tool_name: str = "write_file") -> dict[str, object]:
    return {
        "request_id": "apr-1",
        "session_id": "sess-1",
        "issue_id": "ISS-1",
        "seat_name": "coder",
        "gate_mode": "approval_required",
        "request_type": "tool_approval",
        "reason": f"approval_required_tool:{tool_name}",
        "payload_json": {
            "tool": tool_name,
            "role": "coder",
            "turn_index": 1,
            "control_plane_target_ref": "turn-tool-run:sess-1:ISS-1:coder:0001",
        },
        "status": "pending",
        "resolution_json": {},
        "created_at": "2026-03-03T12:00:00+00:00",
        "updated_at": "2026-03-03T12:00:00+00:00",
        "resolved_at": None,
    }


def _guard_review_row() -> dict[str, object]:
    return {
        "request_id": "grd-1",
        "session_id": "sess-guard-1",
        "issue_id": "ISS-GUARD-1",
        "seat_name": "integrity_guard",
        "gate_mode": "review_required",
        "request_type": "guard_rejection_payload",
        "reason": "missing_rationale",
        "payload_json": {
            "rationale": "",
            "remediation_actions": [],
        },
        "status": "pending",
        "resolution_json": {},
        "created_at": "2026-03-03T13:00:00+00:00",
        "updated_at": "2026-03-03T13:00:00+00:00",
        "resolved_at": None,
    }


def _make_engine(*, rows: list[dict[str, object]] | None = None) -> OrchestrationEngine:
    engine = object.__new__(OrchestrationEngine)
    engine.pending_gates = _FakePendingGates(rows=rows)
    engine.control_plane_repository = InMemoryControlPlaneRecordRepository()
    engine.control_plane_execution_repository = InMemoryControlPlaneExecutionRepository()
    engine.control_plane_publication = ControlPlanePublicationService(repository=engine.control_plane_repository)
    engine.tool_approval_control_plane_operator = ToolApprovalControlPlaneOperatorService(
        publication=engine.control_plane_publication
    )
    return engine


async def _seed_tool_approval_reservation(
    engine: OrchestrationEngine,
    approval_id: str = "apr-1",
    tool_name: str = "write_file",
) -> None:
    service = ToolApprovalControlPlaneReservationService(publication=engine.control_plane_publication)
    await service.publish_pending_tool_approval_hold(
        approval_id=approval_id,
        session_id="sess-1",
        issue_id="ISS-1",
        seat_name="coder",
        tool_name=tool_name,
        turn_index=1,
        created_at="2026-03-03T12:00:00+00:00",
        control_plane_target_ref="turn-tool-run:sess-1:ISS-1:coder:0001",
    )


async def _seed_target_final_truth(engine: OrchestrationEngine) -> None:
    await engine.control_plane_publication.publish_final_truth(
        final_truth_record_id="turn-tool-final-truth:sess-1:ISS-1:coder:0001",
        run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
        result_class=ResultClass.DEGRADED,
        completion_classification=CompletionClassification.PARTIAL,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        degradation_classification=DegradationClassification.DECLARED,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[AuthoritySourceClass.RECONCILIATION_RECORD],
        authoritative_result_ref="turn-tool-result:sess-1:ISS-1:coder:0001",
    )


async def _seed_target_run_execution(engine: OrchestrationEngine) -> None:
    await engine.control_plane_execution_repository.save_run_record(
        record=RunRecord(
            run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
            workload_id="turn-tool-workload:coder",
            workload_version="turn_tool_dispatcher.v1",
            policy_snapshot_id="policy-snapshot-1",
            policy_digest="sha256:policy-1",
            configuration_snapshot_id="config-snapshot-1",
            configuration_digest="sha256:config-1",
            creation_timestamp="2026-03-03T11:59:00+00:00",
            admission_decision_receipt_ref="approval-reservation:apr-1",
            namespace_scope="issue:ISS-1",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
        )
    )
    await engine.control_plane_execution_repository.save_attempt_record(
        record=AttemptRecord(
            attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
            run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
            start_timestamp="2026-03-03T11:59:00+00:00",
        )
    )


async def _seed_target_resource(engine: OrchestrationEngine) -> None:
    await engine.control_plane_publication.publish_resource(
        resource_id="namespace:issue:ISS-1",
        resource_kind="turn_tool_namespace",
        namespace_scope="issue:ISS-1",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_active;namespace:issue:ISS-1",
        last_observed_timestamp="2026-03-03T11:59:05+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref="turn-tool-lease:sess-1:ISS-1:coder:0001",
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )


async def _seed_target_step_and_effect_journal(engine: OrchestrationEngine) -> list[object]:
    await engine.control_plane_execution_repository.save_step_record(
        record=StepRecord(
            step_id="turn-tool-step:sess-1:ISS-1:coder:0001:0001",
            attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
            step_kind="governed_turn_tool_operation",
            namespace_scope="issue:ISS-1",
            input_ref="turn-tool-input:sess-1:ISS-1:coder:0001:0001",
            output_ref="turn-tool-output:sess-1:ISS-1:coder:0001:0001",
            capability_used=CapabilityClass.DESTRUCTIVE_MUTATION,
            resources_touched=["issue:ISS-1", "workspace:path:notes.md"],
            observed_result_classification="tool_operation_observed",
            receipt_refs=["tool-receipt:turn-tool:0001"],
            closure_classification="step_completed",
        )
    )
    first = await engine.control_plane_publication.append_effect_journal_entry(
        journal_entry_id="turn-tool-journal:sess-1:ISS-1:coder:0001:0001",
        effect_id="turn-tool-effect:sess-1:ISS-1:coder:0001:0001",
        run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
        attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
        step_id="turn-tool-step:sess-1:ISS-1:coder:0001:0001",
        authorization_basis_ref="approval-request:apr-1",
        publication_timestamp="2026-03-03T11:59:40+00:00",
        intended_target_ref="issue:ISS-1",
        observed_result_ref="tool-observation:turn-tool:0001",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity:turn-tool-journal:sess-1:ISS-1:coder:0001:0001",
    )
    second = await engine.control_plane_publication.append_effect_journal_entry(
        journal_entry_id="turn-tool-journal:sess-1:ISS-1:coder:0001:0002",
        effect_id="turn-tool-effect:sess-1:ISS-1:coder:0001:0002",
        run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
        attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
        step_id="turn-tool-step:sess-1:ISS-1:coder:0001:0001",
        authorization_basis_ref="approval-request:apr-1",
        publication_timestamp="2026-03-03T11:59:41+00:00",
        intended_target_ref="workspace:path:notes.md",
        observed_result_ref="tool-observation:turn-tool:0002",
        uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        integrity_verification_ref="integrity:turn-tool-journal:sess-1:ISS-1:coder:0001:0002",
        contradictory_entry_refs=["turn-tool-journal:external-conflict"],
        superseding_entry_refs=[first.journal_entry_id],
    )
    return [first, second]


async def _seed_target_checkpoint(engine: OrchestrationEngine, *, journal_entries: list[object] | None = None) -> None:
    dependent_effect_refs = [] if journal_entries is None else [entry.effect_id for entry in journal_entries]
    checkpoint = await engine.control_plane_publication.publish_checkpoint(
        checkpoint=CheckpointRecord(
            checkpoint_id="turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
            parent_ref="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
            creation_timestamp="2026-03-03T11:59:30+00:00",
            state_snapshot_ref="artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
            resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
            invalidation_conditions=["policy_digest_changed"],
            dependent_resource_ids=["issue:ISS-1"],
            dependent_effect_refs=dependent_effect_refs,
            policy_digest="sha256:policy-1",
            integrity_verification_ref="integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
        )
    )
    await engine.control_plane_publication.accept_checkpoint(
        acceptance_id="turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001",
        checkpoint=checkpoint,
        supervisor_authority_ref="turn-tool-supervisor:sess-1:ISS-1:coder:0001",
        decision_timestamp="2026-03-03T11:59:31+00:00",
        required_reobservation_class=CheckpointReobservationClass.NONE,
        integrity_verification_ref="integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001",
        journal_entries=() if journal_entries is None else journal_entries,
        dependent_effect_entry_refs=[] if journal_entries is None else [entry.journal_entry_id for entry in journal_entries],
        dependent_reservation_refs=["approval-reservation:apr-1"],
        dependent_lease_refs=["turn-tool-lease:sess-1:ISS-1:coder:0001"],
    )


async def _seed_guard_review_reservation(engine: OrchestrationEngine, request_id: str = "grd-1") -> None:
    service = ToolApprovalControlPlaneReservationService(publication=engine.control_plane_publication)
    await service.publish_pending_guard_review_hold(
        request_id=request_id,
        session_id="sess-guard-1",
        issue_id="ISS-GUARD-1",
        seat_name="integrity_guard",
        reason="missing_rationale",
        gate_mode="review_required",
        created_at="2026-03-03T13:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_engine_list_approvals_normalizes_rows() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await _seed_target_run_execution(engine)
    await _seed_target_resource(engine)
    journal_entries = await _seed_target_step_and_effect_journal(engine)
    await _seed_target_checkpoint(engine, journal_entries=journal_entries)
    await _seed_target_final_truth(engine)
    items = await engine.list_approvals(status="PENDING", session_id="sess-1", limit=10)
    assert len(items) == 1
    assert items[0]["approval_id"] == "apr-1"
    assert items[0]["status"] == "PENDING"
    assert items[0]["control_plane_target_ref"] == "turn-tool-run:sess-1:ISS-1:coder:0001"
    assert items[0]["control_plane_target_run"]["run_state"] == RunState.EXECUTING.value
    assert items[0]["control_plane_target_run"]["current_attempt_state"] == AttemptState.EXECUTING.value
    assert items[0]["control_plane_target_run"]["namespace_scope"] == "issue:ISS-1"
    assert items[0]["control_plane_target_run"]["admission_decision_receipt_ref"] == "approval-reservation:apr-1"
    assert items[0]["control_plane_target_run"]["policy_snapshot_id"] == "policy-snapshot-1"
    assert items[0]["control_plane_target_run"]["configuration_snapshot_id"] == "config-snapshot-1"
    assert items[0]["control_plane_target_run"]["creation_timestamp"] == "2026-03-03T11:59:00+00:00"
    assert items[0]["control_plane_target_run"]["attempt_count"] == 1
    assert items[0]["control_plane_target_resource"]["resource_id"] == "namespace:issue:ISS-1"
    assert items[0]["control_plane_target_resource"]["resource_kind"] == "turn_tool_namespace"
    assert items[0]["control_plane_target_resource"]["current_observed_state"].startswith(
        "lease_status:lease_active;"
    )
    assert items[0]["control_plane_target_step"]["latest_step_id"] == (
        "turn-tool-step:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_step"]["latest_capability_used"] == CapabilityClass.DESTRUCTIVE_MUTATION.value
    assert items[0]["control_plane_target_step"]["latest_output_ref"] == (
        "turn-tool-output:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_step"]["latest_resources_touched"] == [
        "issue:ISS-1",
        "workspace:path:notes.md",
    ]
    assert items[0]["control_plane_target_step"]["latest_receipt_refs"] == ["tool-receipt:turn-tool:0001"]
    assert items[0]["control_plane_target_checkpoint"]["checkpoint_id"] == (
        "turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_checkpoint"]["creation_timestamp"] == "2026-03-03T11:59:30+00:00"
    assert items[0]["control_plane_target_checkpoint"]["state_snapshot_ref"] == (
        "artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_checkpoint"]["resumability_class"] == (
        CheckpointResumabilityClass.RESUME_FORBIDDEN.value
    )
    assert items[0]["control_plane_target_checkpoint"]["invalidation_conditions"] == ["policy_digest_changed"]
    assert items[0]["control_plane_target_checkpoint"]["dependent_resource_ids"] == ["issue:ISS-1"]
    assert items[0]["control_plane_target_checkpoint"]["dependent_effect_refs"] == [
        "turn-tool-effect:sess-1:ISS-1:coder:0001:0001",
        "turn-tool-effect:sess-1:ISS-1:coder:0001:0002",
    ]
    assert items[0]["control_plane_target_checkpoint"]["policy_digest"] == "sha256:policy-1"
    assert items[0]["control_plane_target_checkpoint"]["integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_checkpoint"]["acceptance_outcome"] == "checkpoint_accepted"
    assert items[0]["control_plane_target_checkpoint"]["acceptance_decision_timestamp"] == (
        "2026-03-03T11:59:31+00:00"
    )
    assert items[0]["control_plane_target_checkpoint"]["acceptance_supervisor_authority_ref"] == (
        "turn-tool-supervisor:sess-1:ISS-1:coder:0001"
    )
    assert items[0]["control_plane_target_checkpoint"]["acceptance_evaluated_policy_digest"] == "sha256:policy-1"
    assert items[0]["control_plane_target_checkpoint"]["required_reobservation_class"] == "no_reobservation_required"
    assert items[0]["control_plane_target_checkpoint"]["acceptance_integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_checkpoint"]["acceptance_dependent_effect_entry_refs"] == [
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001",
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0002",
    ]
    assert items[0]["control_plane_target_checkpoint"]["acceptance_dependent_reservation_refs"] == [
        "approval-reservation:apr-1"
    ]
    assert items[0]["control_plane_target_checkpoint"]["acceptance_dependent_lease_refs"] == [
        "turn-tool-lease:sess-1:ISS-1:coder:0001"
    ]
    assert items[0]["control_plane_target_checkpoint"]["acceptance_rejection_reasons"] == []
    assert items[0]["control_plane_target_effect_journal"]["effect_entry_count"] == 2
    assert items[0]["control_plane_target_effect_journal"]["latest_effect_journal_entry_id"] == (
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0002"
    )
    assert items[0]["control_plane_target_effect_journal"]["latest_publication_sequence"] == 2
    assert items[0]["control_plane_target_effect_journal"]["latest_prior_journal_entry_id"] == (
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001"
    )
    assert items[0]["control_plane_target_effect_journal"]["latest_prior_entry_digest"] == journal_entries[0].entry_digest
    assert items[0]["control_plane_target_effect_journal"]["latest_contradictory_entry_refs"] == [
        "turn-tool-journal:external-conflict"
    ]
    assert items[0]["control_plane_target_effect_journal"]["latest_superseding_entry_refs"] == [
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001"
    ]
    assert items[0]["control_plane_target_effect_journal"]["latest_entry_digest"] == journal_entries[-1].entry_digest
    assert items[0]["control_plane_target_operator_action"] is None
    assert items[0]["control_plane_target_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert items[0]["control_plane_target_reservation"]["status"] == ReservationStatus.ACTIVE.value
    assert items[0]["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "pending_tool_approval:write_file"
    )
    assert items[0]["control_plane_target_reservation"]["supervisor_authority_ref"] == "tool-approval-gate:apr-1:create"
    assert items[0]["control_plane_target_reservation"]["promotion_rule"] is None
    assert items[0]["control_plane_target_final_truth"]["result_class"] == ResultClass.DEGRADED.value
    assert items[0]["control_plane_target_final_truth"]["evidence_sufficiency_classification"] == (
        EvidenceSufficiencyClassification.SUFFICIENT.value
    )
    assert items[0]["control_plane_target_final_truth"]["residual_uncertainty_classification"] == (
        ResidualUncertaintyClassification.BOUNDED.value
    )
    assert items[0]["control_plane_target_final_truth"]["degradation_classification"] == (
        DegradationClassification.DECLARED.value
    )
    assert items[0]["control_plane_target_final_truth"]["terminality_basis"] == "completed_terminal"
    assert items[0]["control_plane_target_final_truth"]["authoritative_result_ref"] == (
        "turn-tool-result:sess-1:ISS-1:coder:0001"
    )
    assert items[0]["control_plane_target_final_truth"]["authority_sources"] == ["reconciliation_record"]
    assert items[0]["control_plane_reservation"]["status"] == ReservationStatus.ACTIVE.value
    assert items[0]["control_plane_reservation"]["expiry_or_invalidation_basis"] == "pending_tool_approval:write_file"
    assert items[0]["control_plane_reservation"]["supervisor_authority_ref"] == "tool-approval-gate:apr-1:create"


@pytest.mark.asyncio
async def test_engine_get_approval_returns_none_when_missing() -> None:
    engine = _make_engine()
    assert await engine.get_approval("missing") is None


@pytest.mark.asyncio
async def test_engine_decide_approval_resolves_pending_item() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await _seed_target_run_execution(engine)
    await _seed_target_resource(engine)
    await _seed_target_checkpoint(engine)
    await _seed_target_final_truth(engine)
    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="approve",
        notes="safe",
        operator_actor_ref="api_key_fingerprint:sha256:test",
    )
    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "APPROVED"
    assert result["approval"]["resolution"]["decision"] == "approve"
    assert result["approval"]["control_plane_target_ref"] == "turn-tool-run:sess-1:ISS-1:coder:0001"
    assert result["approval"]["control_plane_target_run"]["run_state"] == RunState.EXECUTING.value
    assert result["approval"]["control_plane_target_run"]["namespace_scope"] == "issue:ISS-1"
    assert result["approval"]["control_plane_target_run"]["admission_decision_receipt_ref"] == (
        "approval-reservation:apr-1"
    )
    assert result["approval"]["control_plane_target_run"]["policy_snapshot_id"] == "policy-snapshot-1"
    assert result["approval"]["control_plane_target_run"]["configuration_snapshot_id"] == "config-snapshot-1"
    assert result["approval"]["control_plane_target_run"]["creation_timestamp"] == "2026-03-03T11:59:00+00:00"
    assert result["approval"]["control_plane_target_run"]["attempt_count"] == 1
    assert result["approval"]["control_plane_target_resource"]["resource_id"] == "namespace:issue:ISS-1"
    assert result["approval"]["control_plane_target_resource"]["resource_kind"] == "turn_tool_namespace"
    assert result["approval"]["control_plane_target_step"] is None
    assert result["approval"]["control_plane_target_checkpoint"]["checkpoint_id"] == (
        "turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["creation_timestamp"] == "2026-03-03T11:59:30+00:00"
    assert result["approval"]["control_plane_target_checkpoint"]["state_snapshot_ref"] == (
        "artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["invalidation_conditions"] == ["policy_digest_changed"]
    assert result["approval"]["control_plane_target_checkpoint"]["dependent_resource_ids"] == ["issue:ISS-1"]
    assert result["approval"]["control_plane_target_checkpoint"]["dependent_effect_refs"] == []
    assert result["approval"]["control_plane_target_checkpoint"]["policy_digest"] == "sha256:policy-1"
    assert result["approval"]["control_plane_target_checkpoint"]["integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["required_reobservation_class"] == (
        "no_reobservation_required"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["acceptance_integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_effect_journal"] is None
    assert result["approval"]["control_plane_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert result["approval"]["control_plane_operator_action"]["affected_transition_refs"] == [
        "approval-request:apr-1:pending->approved"
    ]
    assert result["approval"]["control_plane_operator_action"]["affected_resource_refs"] == [
        "session:sess-1",
        "issue:ISS-1",
        "namespace:issue:ISS-1",
    ]
    assert result["approval"]["control_plane_target_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert result["approval"]["control_plane_target_operator_action"]["result"] == "approved"
    assert result["approval"]["control_plane_target_operator_action"]["receipt_refs"] == ["approval-request:apr-1"]
    assert result["approval"]["control_plane_target_operator_action"]["affected_transition_refs"] == [
        "turn-tool-run:sess-1:ISS-1:coder:0001:approval:pending->approved"
    ]
    assert result["approval"]["control_plane_target_operator_action"]["affected_resource_refs"] == [
        "session:sess-1",
        "issue:ISS-1",
        "namespace:issue:ISS-1",
        "turn-tool-run:sess-1:ISS-1:coder:0001",
    ]
    assert result["approval"]["control_plane_target_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert result["approval"]["control_plane_target_reservation"]["status"] == ReservationStatus.RELEASED.value
    assert result["approval"]["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert result["approval"]["control_plane_target_reservation"]["supervisor_authority_ref"] == (
        "tool_approval-gate:apr-1:resolve"
    )
    assert result["approval"]["control_plane_target_final_truth"]["closure_basis"] == "reconciliation_closed"
    assert result["approval"]["control_plane_target_final_truth"]["authoritative_result_ref"] == (
        "turn-tool-result:sess-1:ISS-1:coder:0001"
    )
    assert result["approval"]["control_plane_target_final_truth"]["authority_sources"] == ["reconciliation_record"]
    assert result["approval"]["control_plane_reservation"]["status"] == ReservationStatus.RELEASED.value
    assert result["approval"]["control_plane_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert result["approval"]["control_plane_reservation"]["supervisor_authority_ref"] == (
        "tool_approval-gate:apr-1:resolve"
    )
    actions = await engine.control_plane_repository.list_operator_actions(target_ref="approval-request:apr-1")
    run_actions = await engine.control_plane_repository.list_operator_actions(
        target_ref="turn-tool-run:sess-1:ISS-1:coder:0001"
    )
    reservation = await engine.control_plane_repository.get_latest_reservation_record(
        reservation_id="approval-reservation:apr-1"
    )
    assert len(actions) == 1
    assert len(run_actions) == 1
    assert reservation is not None
    assert reservation.status is ReservationStatus.RELEASED
    assert actions[0].result == "approved"
    assert actions[0].actor_ref == "api_key_fingerprint:sha256:test"
    assert run_actions[0].result == "approved"


@pytest.mark.asyncio
async def test_engine_decide_approval_continues_write_file_slice_on_same_session_issue() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await _seed_target_run_execution(engine)
    engine._pipeline = object()
    calls: list[dict[str, object]] = []

    async def _run_card(card_id: str, *, session_id: str | None = None, **_kwargs):
        calls.append({"card_id": card_id, "session_id": session_id})
        return {"ok": True}

    engine.run_card = _run_card

    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="approve",
    )

    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "APPROVED"
    assert calls == [{"card_id": "ISS-1", "session_id": "sess-1"}]


@pytest.mark.asyncio
async def test_engine_decide_approval_continues_create_issue_slice_on_same_session_issue() -> None:
    """Layer: unit."""
    engine = _make_engine(rows=[_tool_approval_row("create_issue")])
    await _seed_tool_approval_reservation(engine, tool_name="create_issue")
    await _seed_target_run_execution(engine)
    engine._pipeline = object()
    calls: list[dict[str, object]] = []

    async def _run_card(card_id: str, *, session_id: str | None = None, **_kwargs):
        calls.append({"card_id": card_id, "session_id": session_id})
        return {"ok": True}

    engine.run_card = _run_card

    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="approve",
    )

    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "APPROVED"
    assert calls == [{"card_id": "ISS-1", "session_id": "sess-1"}]


@pytest.mark.asyncio
async def test_engine_decide_approval_write_file_continuation_fails_closed_on_target_ref_drift() -> None:
    row = _tool_approval_row()
    row["payload_json"] = {
        **dict(row["payload_json"]),
        "control_plane_target_ref": "turn-tool-run:sess-1:ISS-1:coder:9999",
    }
    engine = _make_engine(rows=[row])
    await _seed_tool_approval_reservation(engine)
    engine._pipeline = object()

    async def _run_card(*args, **kwargs):
        return {"ok": True}

    engine.run_card = _run_card

    with pytest.raises(RuntimeError, match="target projection drift"):
        await engine.decide_approval(
            approval_id="apr-1",
            decision="approve",
        )


@pytest.mark.asyncio
async def test_engine_decide_approval_write_file_continuation_fails_closed_on_namespace_drift() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await engine.control_plane_execution_repository.save_run_record(
        record=RunRecord(
            run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
            workload_id="turn-tool-workload:coder",
            workload_version="turn_tool_dispatcher.v1",
            policy_snapshot_id="policy-snapshot-1",
            policy_digest="sha256:policy-1",
            configuration_snapshot_id="config-snapshot-1",
            configuration_digest="sha256:config-1",
            creation_timestamp="2026-03-03T11:59:00+00:00",
            admission_decision_receipt_ref="approval-reservation:apr-1",
            namespace_scope="issue:OTHER",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
        )
    )
    await engine.control_plane_execution_repository.save_attempt_record(
        record=AttemptRecord(
            attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
            run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
            start_timestamp="2026-03-03T11:59:00+00:00",
        )
    )
    engine._pipeline = object()

    async def _run_card(*args, **kwargs):
        return {"ok": True}

    engine.run_card = _run_card

    with pytest.raises(RuntimeError, match="namespace scope drifted"):
        await engine.decide_approval(
            approval_id="apr-1",
            decision="approve",
        )


@pytest.mark.asyncio
async def test_engine_decide_approval_rejects_non_packet1_decision_token() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)

    with pytest.raises(ValueError, match="approve, deny"):
        await engine.decide_approval(
            approval_id="apr-1",
            decision="edit",
            edited_proposal={"path": "notes.md"},
        )

    approval = await engine.get_approval("apr-1")
    assert approval is not None
    assert approval["status"] == "PENDING"


@pytest.mark.asyncio
async def test_engine_decide_approval_conflict_after_resolution_raises() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await engine.decide_approval(approval_id="apr-1", decision="approve")
    with pytest.raises(RuntimeError):
        await engine.decide_approval(approval_id="apr-1", decision="deny")


@pytest.mark.asyncio
async def test_engine_decide_approval_publishes_terminal_operator_command_for_denial() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await _seed_target_run_execution(engine)
    await _seed_target_resource(engine)
    await _seed_target_checkpoint(engine)
    await _seed_target_final_truth(engine)
    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="deny",
        operator_actor_ref="api_key_fingerprint:sha256:test",
    )
    assert result["approval"]["status"] == "DENIED"
    assert result["approval"]["control_plane_target_ref"] == "turn-tool-run:sess-1:ISS-1:coder:0001"
    assert result["approval"]["control_plane_target_run"]["current_attempt_state"] == AttemptState.EXECUTING.value
    assert result["approval"]["control_plane_target_run"]["namespace_scope"] == "issue:ISS-1"
    assert result["approval"]["control_plane_target_run"]["policy_snapshot_id"] == "policy-snapshot-1"
    assert result["approval"]["control_plane_target_run"]["configuration_snapshot_id"] == "config-snapshot-1"
    assert result["approval"]["control_plane_target_run"]["creation_timestamp"] == "2026-03-03T11:59:00+00:00"
    assert result["approval"]["control_plane_target_run"]["attempt_count"] == 1
    assert result["approval"]["control_plane_target_resource"]["resource_id"] == "namespace:issue:ISS-1"
    assert result["approval"]["control_plane_target_resource"]["resource_kind"] == "turn_tool_namespace"
    assert result["approval"]["control_plane_target_step"] is None
    assert result["approval"]["control_plane_target_checkpoint"]["checkpoint_id"] == (
        "turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["creation_timestamp"] == "2026-03-03T11:59:30+00:00"
    assert result["approval"]["control_plane_target_checkpoint"]["state_snapshot_ref"] == (
        "artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["invalidation_conditions"] == ["policy_digest_changed"]
    assert result["approval"]["control_plane_target_checkpoint"]["dependent_resource_ids"] == ["issue:ISS-1"]
    assert result["approval"]["control_plane_target_checkpoint"]["dependent_effect_refs"] == []
    assert result["approval"]["control_plane_target_checkpoint"]["policy_digest"] == "sha256:policy-1"
    assert result["approval"]["control_plane_target_checkpoint"]["integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["required_reobservation_class"] == (
        "no_reobservation_required"
    )
    assert result["approval"]["control_plane_target_checkpoint"]["acceptance_integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001"
    )
    assert result["approval"]["control_plane_target_effect_journal"] is None
    assert result["approval"]["control_plane_operator_action"]["input_class"] == "operator_command"
    assert result["approval"]["control_plane_operator_action"]["affected_transition_refs"] == [
        "approval-request:apr-1:pending->denied"
    ]
    assert result["approval"]["control_plane_target_operator_action"]["input_class"] == "operator_command"
    assert result["approval"]["control_plane_target_operator_action"]["result"] == "denied"
    assert result["approval"]["control_plane_target_operator_action"]["receipt_refs"] == ["approval-request:apr-1"]
    assert result["approval"]["control_plane_target_operator_action"]["affected_transition_refs"] == [
        "turn-tool-run:sess-1:ISS-1:coder:0001:approval:pending->denied"
    ]
    assert result["approval"]["control_plane_target_operator_action"]["affected_resource_refs"] == [
        "session:sess-1",
        "issue:ISS-1",
        "namespace:issue:ISS-1",
        "turn-tool-run:sess-1:ISS-1:coder:0001",
    ]
    assert result["approval"]["control_plane_target_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert result["approval"]["control_plane_target_reservation"]["status"] == ReservationStatus.INVALIDATED.value
    assert result["approval"]["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_denied_terminal_stop"
    )
    assert result["approval"]["control_plane_target_reservation"]["supervisor_authority_ref"] == (
        "tool_approval-gate:apr-1:resolve"
    )
    assert result["approval"]["control_plane_target_final_truth"]["result_class"] == ResultClass.DEGRADED.value
    assert result["approval"]["control_plane_target_final_truth"]["terminality_basis"] == "completed_terminal"
    assert result["approval"]["control_plane_reservation"]["status"] == ReservationStatus.INVALIDATED.value
    assert result["approval"]["control_plane_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_denied_terminal_stop"
    )
    assert result["approval"]["control_plane_reservation"]["supervisor_authority_ref"] == (
        "tool_approval-gate:apr-1:resolve"
    )
    actions = await engine.control_plane_repository.list_operator_actions(target_ref="approval-request:apr-1")
    run_actions = await engine.control_plane_repository.list_operator_actions(
        target_ref="turn-tool-run:sess-1:ISS-1:coder:0001"
    )
    reservation = await engine.control_plane_repository.get_latest_reservation_record(
        reservation_id="approval-reservation:apr-1"
    )
    assert len(actions) == 1
    assert len(run_actions) == 1
    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert actions[0].result == "denied"
    assert run_actions[0].result == "denied"


@pytest.mark.asyncio
async def test_engine_decide_approval_denial_closes_open_write_file_governed_run() -> None:
    engine = _make_engine()
    await _seed_tool_approval_reservation(engine)
    await _seed_target_run_execution(engine)

    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="deny",
    )

    run = await engine.control_plane_execution_repository.get_run_record(run_id="turn-tool-run:sess-1:ISS-1:coder:0001")
    attempt = None if run is None else await engine.control_plane_execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await engine.control_plane_publication.repository.get_final_truth(
        run_id="turn-tool-run:sess-1:ISS-1:coder:0001"
    )

    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "DENIED"
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.authoritative_result_ref == "approval-request:apr-1:denied"


@pytest.mark.asyncio
async def test_engine_decide_approval_denial_closes_open_create_issue_governed_run() -> None:
    """Layer: unit."""
    engine = _make_engine(rows=[_tool_approval_row("create_issue")])
    await _seed_tool_approval_reservation(engine, tool_name="create_issue")
    await _seed_target_run_execution(engine)

    result = await engine.decide_approval(
        approval_id="apr-1",
        decision="deny",
    )

    run = await engine.control_plane_execution_repository.get_run_record(run_id="turn-tool-run:sess-1:ISS-1:coder:0001")
    attempt = None if run is None else await engine.control_plane_execution_repository.get_attempt_record(
        attempt_id=str(run.current_attempt_id or "")
    )
    truth = await engine.control_plane_publication.repository.get_final_truth(
        run_id="turn-tool-run:sess-1:ISS-1:coder:0001"
    )

    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "DENIED"
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.FAILED
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.authoritative_result_ref == "approval-request:apr-1:denied"


@pytest.mark.asyncio
async def test_engine_decide_approval_resolves_guard_review_hold_without_tool_operator_action() -> None:
    engine = _make_engine(rows=[_guard_review_row()])
    await _seed_guard_review_reservation(engine)

    result = await engine.decide_approval(
        approval_id="grd-1",
        decision="approve",
        operator_actor_ref="api_key_fingerprint:sha256:test",
    )

    assert result["status"] == "resolved"
    assert result["approval"]["status"] == "APPROVED"
    assert result["approval"]["control_plane_target_ref"] is None
    assert result["approval"]["control_plane_target_run"] is None
    assert result["approval"]["control_plane_target_step"] is None
    assert result["approval"]["control_plane_target_operator_action"] is None
    assert result["approval"]["control_plane_target_reservation"] is None
    assert result["approval"]["control_plane_target_final_truth"] is None
    assert result["approval"]["control_plane_operator_action"]["input_class"] == "operator_command"
    assert result["approval"]["control_plane_operator_action"]["command_class"] == "approve_continue"
    assert result["approval"]["control_plane_reservation"]["status"] == ReservationStatus.RELEASED.value
    assert result["approval"]["control_plane_reservation"]["expiry_or_invalidation_basis"] == (
        "pending_gate_resolved_continue:guard_rejection_payload:approved"
    )
    assert result["approval"]["control_plane_reservation"]["supervisor_authority_ref"] == (
        "guard_rejection_payload-gate:grd-1:resolve"
    )
    reservation = await engine.control_plane_repository.get_latest_reservation_record(
        reservation_id="approval-reservation:grd-1"
    )
    actions = await engine.control_plane_repository.list_operator_actions(target_ref="approval-request:grd-1")
    assert reservation is not None
    assert reservation.status is ReservationStatus.RELEASED
    assert len(actions) == 1
    assert actions[0].result == "approved"


@pytest.mark.asyncio
async def test_engine_approvals_use_nervous_system_runtime_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    reset_runtime_state_for_tests()
    admit_proposal_v1(
        {
            "contract_version": "kernel_api/v1",
            "session_id": "sess-ns-engine-1",
            "trace_id": "trace-ns-engine-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )

    engine = object.__new__(OrchestrationEngine)
    engine.control_plane_repository = InMemoryControlPlaneRecordRepository()
    engine.control_plane_publication = ControlPlanePublicationService(repository=engine.control_plane_repository)
    engine.tool_approval_control_plane_operator = ToolApprovalControlPlaneOperatorService(
        publication=engine.control_plane_publication
    )
    items = await engine.list_approvals(status="PENDING", session_id="sess-ns-engine-1", limit=10)
    assert len(items) == 1
    approval_id = items[0]["approval_id"]

    resolved = await engine.decide_approval(
        approval_id=approval_id,
        decision="approve",
        operator_actor_ref="api_key_fingerprint:sha256:test",
    )
    assert resolved["approval"]["status"] == "APPROVED"
    assert resolved["approval"]["control_plane_operator_action"]["result"] == "approved"
    actions = await engine.control_plane_repository.list_operator_actions(
        target_ref=f"approval-request:{approval_id}"
    )
    assert len(actions) == 1
