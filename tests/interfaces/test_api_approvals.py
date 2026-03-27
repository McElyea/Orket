from __future__ import annotations

from fastapi.testclient import TestClient

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.pending_gate_control_plane_operator_service import (
    PendingGateControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ReservationKind,
    ReservationStatus,
    ResidualUncertaintyClassification,
    ResultClass,
)
from orket.interfaces.api import app
import orket.interfaces.api as api_module
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests
from tests.application.test_engine_approvals import (
    _FakePendingGates,
    _guard_review_row,
    _seed_target_step_and_effect_journal,
    _tool_approval_row,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


client = TestClient(app)


def test_list_approvals_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_list_approvals(*, status=None, session_id=None, request_id=None, limit=100):
        captured["status"] = status
        captured["session_id"] = session_id
        captured["request_id"] = request_id
        captured["limit"] = limit
        return [{"approval_id": "abc123", "status": "PENDING"}]

    monkeypatch.setattr(api_module.engine, "list_approvals", fake_list_approvals)

    response = client.get(
        "/v1/approvals?status=PENDING&session_id=sess-1&request_id=req-1&limit=20",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["approval_id"] == "abc123"
    assert captured == {
        "status": "PENDING",
        "session_id": "sess-1",
        "request_id": "req-1",
        "limit": 20,
    }


def test_get_approval_returns_404_when_missing(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_approval(_approval_id: str):
        return None

    monkeypatch.setattr(api_module.engine, "get_approval", fake_get_approval)
    response = client.get("/v1/approvals/missing", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_decide_approval_returns_409_on_conflict(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_decide_approval(
        *,
        approval_id: str,
        decision: str,
        edited_proposal=None,
        notes=None,
        operator_actor_ref=None,
    ):
        _ = approval_id, decision, edited_proposal, notes, operator_actor_ref
        raise RuntimeError("approval already resolved with a conflicting decision")

    monkeypatch.setattr(api_module.engine, "decide_approval", fake_decide_approval)
    response = client.post(
        "/v1/approvals/abc123/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve"},
    )
    assert response.status_code == 409


def test_decide_approval_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_decide_approval(
        *,
        approval_id: str,
        decision: str,
        edited_proposal=None,
        notes=None,
        operator_actor_ref=None,
    ):
        captured["approval_id"] = approval_id
        captured["decision"] = decision
        captured["edited_proposal"] = edited_proposal
        captured["notes"] = notes
        captured["operator_actor_ref"] = operator_actor_ref
        return {"status": "resolved", "approval": {"approval_id": approval_id, "status": "APPROVED"}}

    monkeypatch.setattr(api_module.engine, "decide_approval", fake_decide_approval)
    response = client.post(
        "/v1/approvals/abc123/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve", "notes": "safe", "edited_proposal": {"path": "a.txt"}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert captured == {
        "approval_id": "abc123",
        "decision": "approve",
        "edited_proposal": {"path": "a.txt"},
        "notes": "safe",
        "operator_actor_ref": api_module._api_key_actor_ref("test-key"),
    }


def test_approvals_endpoints_real_nervous_system_flow(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    reset_runtime_state_for_tests()
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication, raising=False)
    monkeypatch.setattr(
        api_module.engine,
        "tool_approval_control_plane_operator",
        ToolApprovalControlPlaneOperatorService(publication=publication),
        raising=False,
    )

    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-approvals-real-1",
            "trace_id": "trace-api-approvals-real-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        },
    )
    assert admitted.status_code == 200
    approval_id = admitted.json()["approval_id"]
    assert repository.reservations_by_id[f"approval-reservation:{approval_id}"][-1].status.value == "reservation_active"

    listed = client.get(
        "/v1/approvals?status=PENDING&session_id=sess-api-approvals-real-1",
        headers={"X-API-Key": "test-key"},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
    assert any(item["approval_id"] == approval_id for item in listed.json()["items"])

    decided = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve", "notes": "api-approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["approval"]["status"] == "APPROVED"
    assert decided.json()["approval"]["control_plane_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert decided.json()["approval"]["control_plane_target_ref"] == (
        "kernel-action-run:sess-api-approvals-real-1:trace-api-approvals-real-1"
    )
    assert decided.json()["approval"]["control_plane_target_run"]["namespace_scope"] == (
        "session:sess-api-approvals-real-1"
    )
    assert decided.json()["approval"]["control_plane_target_run"]["policy_snapshot_id"] == (
        "kernel-admission-decision:sess-api-approvals-real-1:trace-api-approvals-real-1"
    )
    assert decided.json()["approval"]["control_plane_target_run"]["configuration_snapshot_id"] == (
        "kernel-proposal:sess-api-approvals-real-1:trace-api-approvals-real-1"
    )
    assert decided.json()["approval"]["control_plane_target_run"]["creation_timestamp"]
    assert decided.json()["approval"]["control_plane_target_run"]["attempt_count"] == 1
    assert decided.json()["approval"]["control_plane_target_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert decided.json()["approval"]["control_plane_target_operator_action"]["result"] == "approved"
    assert decided.json()["approval"]["control_plane_target_operator_action"]["receipt_refs"] == [
        f"approval-request:{approval_id}"
    ]
    assert decided.json()["approval"]["control_plane_target_operator_action"]["affected_transition_refs"] == [
        "kernel-action-run:sess-api-approvals-real-1:trace-api-approvals-real-1:approval:pending->approved"
    ]
    assert decided.json()["approval"]["control_plane_target_reservation"]["reservation_kind"] == (
        "operator_hold_reservation"
    )
    assert decided.json()["approval"]["control_plane_target_reservation"]["status"] == "reservation_released"
    assert decided.json()["approval"]["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert decided.json()["approval"]["control_plane_target_reservation"]["supervisor_authority_ref"] == (
        f"tool_approval-gate:{approval_id}:resolve"
    )
    assert decided.json()["approval"]["control_plane_target_final_truth"] is None
    assert decided.json()["approval"]["control_plane_reservation"]["status"] == "reservation_released"
    assert decided.json()["approval"]["control_plane_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert decided.json()["approval"]["control_plane_reservation"]["supervisor_authority_ref"] == (
        f"tool_approval-gate:{approval_id}:resolve"
    )
    assert any(
        record.target_ref == f"approval-request:{approval_id}"
        for record in repository.operator_action_by_id.values()
    )
    assert any(
        record.target_ref == "kernel-action-run:sess-api-approvals-real-1:trace-api-approvals-real-1"
        for record in repository.operator_action_by_id.values()
    )


def test_tool_approval_api_exposes_target_ref_and_target_operator_action(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    repository = InMemoryControlPlaneRecordRepository()
    execution_repository = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=repository)
    monkeypatch.setattr(api_module.engine, "pending_gates", _FakePendingGates(rows=[_tool_approval_row()]), raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_execution_repository", execution_repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication, raising=False)
    monkeypatch.setattr(
        api_module.engine,
        "tool_approval_control_plane_operator",
        ToolApprovalControlPlaneOperatorService(publication=publication),
        raising=False,
    )
    monkeypatch.setattr(
        api_module.engine,
        "tool_approval_control_plane_reservation",
        ToolApprovalControlPlaneReservationService(publication=publication),
        raising=False,
    )

    import asyncio
    from orket.core.contracts.control_plane_models import AttemptRecord, CheckpointRecord, RunRecord
    from orket.core.domain import AttemptState, RunState

    asyncio.run(
        execution_repository.save_run_record(
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
    )
    asyncio.run(
        execution_repository.save_attempt_record(
            record=AttemptRecord(
                attempt_id="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
                run_id="turn-tool-run:sess-1:ISS-1:coder:0001",
                attempt_ordinal=1,
                attempt_state=AttemptState.EXECUTING,
                starting_state_snapshot_ref="turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
                start_timestamp="2026-03-03T11:59:00+00:00",
            )
        )
    )
    journal_entries = asyncio.run(_seed_target_step_and_effect_journal(api_module.engine))
    asyncio.run(
        publication.accept_checkpoint(
            acceptance_id="turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001",
            checkpoint=CheckpointRecord(
                checkpoint_id="turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
                parent_ref="turn-tool-attempt:sess-1:ISS-1:coder:0001:0001",
                creation_timestamp="2026-03-03T11:59:30+00:00",
                state_snapshot_ref="artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
                resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
                invalidation_conditions=["policy_digest_changed"],
                dependent_resource_ids=["issue:ISS-1"],
                dependent_effect_refs=[entry.effect_id for entry in journal_entries],
                policy_digest="sha256:policy-1",
                integrity_verification_ref="integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001",
            ),
            supervisor_authority_ref="turn-tool-supervisor:sess-1:ISS-1:coder:0001",
            decision_timestamp="2026-03-03T11:59:31+00:00",
            required_reobservation_class=CheckpointReobservationClass.NONE,
            integrity_verification_ref="integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001",
            journal_entries=journal_entries,
            dependent_effect_entry_refs=[entry.journal_entry_id for entry in journal_entries],
            dependent_reservation_refs=["approval-reservation:apr-1"],
            dependent_lease_refs=["turn-tool-lease:sess-1:ISS-1:coder:0001"],
        )
    )
    asyncio.run(
        api_module.engine.tool_approval_control_plane_reservation.publish_pending_tool_approval_hold(
            approval_id="apr-1",
            session_id="sess-1",
            issue_id="ISS-1",
            seat_name="coder",
            tool_name="write_file",
            turn_index=1,
            created_at="2026-03-03T12:00:00+00:00",
            control_plane_target_ref="turn-tool-run:sess-1:ISS-1:coder:0001",
        )
    )
    asyncio.run(
        publication.publish_final_truth(
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
    )

    decided = client.post(
        "/v1/approvals/apr-1/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve"},
    )

    assert decided.status_code == 200
    approval = decided.json()["approval"]
    assert approval["control_plane_target_ref"] == "turn-tool-run:sess-1:ISS-1:coder:0001"
    assert approval["control_plane_target_run"]["run_state"] == "executing"
    assert approval["control_plane_target_run"]["current_attempt_state"] == "attempt_executing"
    assert approval["control_plane_target_run"]["namespace_scope"] == "issue:ISS-1"
    assert approval["control_plane_target_run"]["admission_decision_receipt_ref"] == "approval-reservation:apr-1"
    assert approval["control_plane_target_run"]["policy_snapshot_id"] == "policy-snapshot-1"
    assert approval["control_plane_target_run"]["configuration_snapshot_id"] == "config-snapshot-1"
    assert approval["control_plane_target_run"]["creation_timestamp"] == "2026-03-03T11:59:00+00:00"
    assert approval["control_plane_target_run"]["attempt_count"] == 1
    assert approval["control_plane_target_step"]["latest_step_id"] == "turn-tool-step:sess-1:ISS-1:coder:0001:0001"
    assert approval["control_plane_target_step"]["latest_capability_used"] == "destructive_mutation"
    assert approval["control_plane_target_step"]["latest_output_ref"] == (
        "turn-tool-output:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_step"]["latest_resources_touched"] == [
        "issue:ISS-1",
        "workspace:path:notes.md",
    ]
    assert approval["control_plane_target_step"]["latest_receipt_refs"] == ["tool-receipt:turn-tool:0001"]
    assert approval["control_plane_target_checkpoint"]["checkpoint_id"] == (
        "turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_checkpoint"]["creation_timestamp"] == "2026-03-03T11:59:30+00:00"
    assert approval["control_plane_target_checkpoint"]["state_snapshot_ref"] == (
        "artifact:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_checkpoint"]["resumability_class"] == "resume_forbidden"
    assert approval["control_plane_target_checkpoint"]["acceptance_outcome"] == "checkpoint_accepted"
    assert approval["control_plane_target_checkpoint"]["invalidation_conditions"] == ["policy_digest_changed"]
    assert approval["control_plane_target_checkpoint"]["dependent_resource_ids"] == ["issue:ISS-1"]
    assert approval["control_plane_target_checkpoint"]["dependent_effect_refs"] == [
        "turn-tool-effect:sess-1:ISS-1:coder:0001:0001",
        "turn-tool-effect:sess-1:ISS-1:coder:0001:0002",
    ]
    assert approval["control_plane_target_checkpoint"]["policy_digest"] == "sha256:policy-1"
    assert approval["control_plane_target_checkpoint"]["integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_checkpoint"]["acceptance_decision_timestamp"] == "2026-03-03T11:59:31+00:00"
    assert approval["control_plane_target_checkpoint"]["acceptance_supervisor_authority_ref"] == (
        "turn-tool-supervisor:sess-1:ISS-1:coder:0001"
    )
    assert approval["control_plane_target_checkpoint"]["acceptance_evaluated_policy_digest"] == "sha256:policy-1"
    assert approval["control_plane_target_checkpoint"]["required_reobservation_class"] == "no_reobservation_required"
    assert approval["control_plane_target_checkpoint"]["acceptance_integrity_verification_ref"] == (
        "integrity:turn-tool-checkpoint-acceptance:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_checkpoint"]["acceptance_dependent_effect_entry_refs"] == [
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001",
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0002",
    ]
    assert approval["control_plane_target_checkpoint"]["acceptance_dependent_reservation_refs"] == [
        "approval-reservation:apr-1"
    ]
    assert approval["control_plane_target_checkpoint"]["acceptance_dependent_lease_refs"] == [
        "turn-tool-lease:sess-1:ISS-1:coder:0001"
    ]
    assert approval["control_plane_target_checkpoint"]["acceptance_rejection_reasons"] == []
    assert approval["control_plane_target_effect_journal"]["effect_entry_count"] == 2
    assert approval["control_plane_target_effect_journal"]["latest_publication_sequence"] == 2
    assert approval["control_plane_target_effect_journal"]["latest_prior_journal_entry_id"] == (
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001"
    )
    assert approval["control_plane_target_effect_journal"]["latest_prior_entry_digest"] == journal_entries[0].entry_digest
    assert approval["control_plane_target_effect_journal"]["latest_contradictory_entry_refs"] == [
        "turn-tool-journal:external-conflict"
    ]
    assert approval["control_plane_target_effect_journal"]["latest_superseding_entry_refs"] == [
        "turn-tool-journal:sess-1:ISS-1:coder:0001:0001"
    ]
    assert approval["control_plane_target_effect_journal"]["latest_entry_digest"] == journal_entries[-1].entry_digest
    assert approval["control_plane_target_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert approval["control_plane_target_operator_action"]["result"] == "approved"
    assert approval["control_plane_target_operator_action"]["receipt_refs"] == ["approval-request:apr-1"]
    assert approval["control_plane_target_operator_action"]["affected_transition_refs"] == [
        "turn-tool-run:sess-1:ISS-1:coder:0001:approval:pending->approved"
    ]
    assert approval["control_plane_target_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert approval["control_plane_target_reservation"]["status"] == "reservation_released"
    assert approval["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert approval["control_plane_target_reservation"]["supervisor_authority_ref"] == (
        "tool_approval-gate:apr-1:resolve"
    )
    assert approval["control_plane_target_final_truth"]["result_class"] == "degraded"
    assert approval["control_plane_target_final_truth"]["evidence_sufficiency_classification"] == "evidence_sufficient"
    assert approval["control_plane_target_final_truth"]["residual_uncertainty_classification"] == (
        "bounded_residual_uncertainty"
    )
    assert approval["control_plane_target_final_truth"]["degradation_classification"] == "declared_degradation"
    assert approval["control_plane_target_final_truth"]["terminality_basis"] == "completed_terminal"
    assert approval["control_plane_target_final_truth"]["authoritative_result_ref"] == (
        "turn-tool-result:sess-1:ISS-1:coder:0001"
    )
    assert approval["control_plane_target_final_truth"]["authority_sources"] == ["reconciliation_record"]


def test_guard_review_decision_publishes_operator_command(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    monkeypatch.setattr(api_module.engine, "pending_gates", _FakePendingGates(rows=[_guard_review_row()]), raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication, raising=False)
    monkeypatch.setattr(
        api_module.engine,
        "pending_gate_control_plane_operator",
        PendingGateControlPlaneOperatorService(publication=publication),
        raising=False,
    )

    import asyncio

    asyncio.run(
        publication.publish_reservation(
            reservation_id="approval-reservation:grd-1",
            holder_ref="approval-request:grd-1",
            reservation_kind=ReservationKind.OPERATOR_HOLD,
            target_scope_ref=(
                "operator-hold:approval=approval-request:grd-1;"
                "seat=integrity_guard;reason=missing_rationale;"
                "request_type=guard_rejection_payload;gate_mode=review_required;"
                "session=sess-guard-1;issue=ISS-GUARD-1"
            ),
            creation_timestamp="2026-03-03T13:00:00+00:00",
            expiry_or_invalidation_basis="pending_guard_review:missing_rationale",
            status=ReservationStatus.ACTIVE,
            supervisor_authority_ref="guard-review-gate:grd-1:create",
        )
    )

    response = client.post(
        "/v1/approvals/grd-1/decision",
        headers={"X-API-Key": "test-key"},
        json={"decision": "approve", "notes": "looks good"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["approval"]["status"] == "APPROVED"
    assert payload["approval"]["control_plane_target_ref"] is None
    assert payload["approval"]["control_plane_target_operator_action"] is None
    assert payload["approval"]["control_plane_target_final_truth"] is None
    assert payload["approval"]["control_plane_target_step"] is None
    assert payload["approval"]["control_plane_operator_action"]["input_class"] == "operator_command"
    assert payload["approval"]["control_plane_operator_action"]["command_class"] == "approve_continue"
    assert payload["approval"]["control_plane_reservation"]["status"] == "reservation_released"
