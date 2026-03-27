# Layer: integration

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.interfaces.api import app
import orket.interfaces.api as api_module
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.integration


client = TestClient(app)


def test_kernel_operator_surfaces_cover_one_action_lifecycle(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "true")
    monkeypatch.delenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", raising=False)
    reset_runtime_state_for_tests()
    repository = InMemoryControlPlaneRecordRepository()
    execution_repository = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=repository)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_execution_repository", execution_repository, raising=False)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication, raising=False)
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane",
        KernelActionControlPlaneService(
            execution_repository=execution_repository,
            publication=publication,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_view",
        KernelActionControlPlaneViewService(
            record_repository=repository,
            execution_repository=execution_repository,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        api_module.engine,
        "tool_approval_control_plane_operator",
        ToolApprovalControlPlaneOperatorService(publication=publication),
        raising=False,
    )

    headers = {"X-API-Key": "test-key"}
    session_id = "sess-api-operator-surfaces"
    trace_id = "trace-api-operator-surfaces"

    projection = client.post(
        "/v1/kernel/projection-pack",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "purpose": "action_path",
            "tool_context_summary": {"tool": "fs.write_patch"},
            "policy_context": {"mode": "strict"},
        },
    )
    assert projection.status_code == 200

    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {
                    "tool_name": "fs.write_patch",
                    "args": {"path": "./workspace/notes.md", "patch": "ADD LINE hello"},
                },
            },
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()
    assert admitted_payload["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert admitted_payload["admission_decision"]["reason_codes"] == ["APPROVAL_REQUIRED_DESTRUCTIVE"]
    approval_id = admitted_payload["approval_id"]
    assert repository.reservations_by_id[f"approval-reservation:{approval_id}"][-1].status.value == "reservation_active"

    decided = client.post(
        f"/v1/approvals/{approval_id}/decision",
        headers=headers,
        json={"decision": "approve", "notes": "api-approved"},
    )
    assert decided.status_code == 200
    assert decided.json()["approval"]["status"] == "APPROVED"

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers=headers,
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "approval_id": approval_id,
            "execution_result_digest": "2" * 64,
        },
    )
    assert committed.status_code == 200
    assert committed.json()["status"] == "COMMITTED"

    approvals = client.get("/v1/approvals", headers=headers, params={"session_id": session_id, "limit": 20})
    ledger = client.get(
        "/v1/kernel/ledger-events",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id, "limit": 200},
    )
    rebuild = client.post("/v1/kernel/approvals/rebuild", headers=headers, json={"session_id": session_id})
    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id},
    )
    audit = client.get(
        "/v1/kernel/action-lifecycle/audit",
        headers=headers,
        params={"session_id": session_id, "trace_id": trace_id},
    )

    assert approvals.status_code == 200
    assert ledger.status_code == 200
    assert rebuild.status_code == 200
    assert replay.status_code == 200
    assert audit.status_code == 200

    approval_rows = [
        row
        for row in list(approvals.json().get("items") or [])
        if row.get("approval_id") == approval_id
    ]
    assert approval_rows
    assert approval_rows[0]["status"] == "APPROVED"
    assert approval_rows[0]["control_plane_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert approval_rows[0]["control_plane_operator_action"]["affected_resource_refs"] == [
        f"session:{session_id}",
        f"kernel-action-scope:session:{session_id}",
    ]
    assert approval_rows[0]["control_plane_reservation"]["status"] == "reservation_released"
    assert approval_rows[0]["control_plane_target_ref"] == (
        f"kernel-action-run:{session_id}:{trace_id}"
    )
    assert approval_rows[0]["control_plane_target_run"]["run_state"] == "completed"
    assert approval_rows[0]["control_plane_target_run"]["current_attempt_state"] == "attempt_completed"
    assert approval_rows[0]["control_plane_target_run"]["namespace_scope"] == (
        f"session:{session_id}"
    )
    assert approval_rows[0]["control_plane_target_run"]["policy_snapshot_id"] == (
        f"kernel-admission-decision:{session_id}:{trace_id}"
    )
    assert approval_rows[0]["control_plane_target_run"]["configuration_snapshot_id"] == (
        f"kernel-proposal:{session_id}:{trace_id}"
    )
    assert approval_rows[0]["control_plane_target_run"]["creation_timestamp"]
    assert approval_rows[0]["control_plane_target_run"]["attempt_count"] == 1
    assert approval_rows[0]["control_plane_target_step"]["step_count"] == 1
    assert approval_rows[0]["control_plane_target_step"]["latest_step_id"] == (
        f"kernel-action-step:kernel-action-run:{session_id}:{trace_id}:commit"
    )
    assert approval_rows[0]["control_plane_target_step"]["latest_namespace_scope"] == (
        f"session:{session_id}"
    )
    assert approval_rows[0]["control_plane_target_step"]["latest_capability_used"] is None
    assert approval_rows[0]["control_plane_target_step"]["latest_output_ref"] == (
        f"kernel-execution-result:{'2' * 64}"
    )
    assert approval_rows[0]["control_plane_target_step"]["latest_resources_touched"] == [
        f"kernel-action-target:{session_id}:{trace_id}"
    ]
    assert approval_rows[0]["control_plane_target_step"]["latest_receipt_refs"] == [
        f"kernel-ledger-event:{committed.json()['commit_event_digest']}"
    ]
    assert approval_rows[0]["control_plane_target_checkpoint"] is None
    assert approval_rows[0]["control_plane_target_effect_journal"]["effect_entry_count"] == 1
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_effect_journal_entry_id"] == (
        f"kernel-action-journal:kernel-action-run:{session_id}:{trace_id}:commit"
    )
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_step_id"] == (
        f"kernel-action-step:kernel-action-run:{session_id}:{trace_id}:commit"
    )
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_publication_sequence"] == 1
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_intended_target_ref"] == (
        f"kernel-action-target:{session_id}:{trace_id}"
    )
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_authorization_basis_ref"].startswith(
        "kernel-authorization:"
    )
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_publication_timestamp"]
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_integrity_verification_ref"] == (
        f"kernel-ledger-event:{committed.json()['commit_event_digest']}"
    )
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_prior_journal_entry_id"] is None
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_prior_entry_digest"] is None
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_contradictory_entry_refs"] == []
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_superseding_entry_refs"] == []
    assert len(approval_rows[0]["control_plane_target_effect_journal"]["latest_entry_digest"]) == 64
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_observed_result_ref"] is None
    assert approval_rows[0]["control_plane_target_effect_journal"]["latest_uncertainty_classification"] == (
        "unresolved_residual_uncertainty"
    )
    assert approval_rows[0]["control_plane_target_operator_action"]["input_class"] == "operator_risk_acceptance"
    assert approval_rows[0]["control_plane_target_operator_action"]["receipt_refs"] == [f"approval-request:{approval_id}"]
    assert approval_rows[0]["control_plane_target_operator_action"]["affected_transition_refs"] == [
        f"kernel-action-run:{session_id}:{trace_id}:approval:pending->approved"
    ]
    assert approval_rows[0]["control_plane_target_operator_action"]["affected_resource_refs"] == [
        f"session:{session_id}",
        f"kernel-action-scope:session:{session_id}",
        f"kernel-action-run:{session_id}:{trace_id}",
    ]
    assert approval_rows[0]["control_plane_target_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert approval_rows[0]["control_plane_target_reservation"]["status"] == "reservation_released"
    assert approval_rows[0]["control_plane_target_reservation"]["expiry_or_invalidation_basis"] == (
        "approval_resolved_continue:approved"
    )
    assert approval_rows[0]["control_plane_target_reservation"]["supervisor_authority_ref"] == (
        f"tool_approval-gate:{approval_id}:resolve"
    )
    assert approval_rows[0]["control_plane_target_final_truth"]["result_class"] == "degraded"
    assert approval_rows[0]["control_plane_target_final_truth"]["evidence_sufficiency_classification"] == (
        "evidence_insufficient"
    )
    assert approval_rows[0]["control_plane_target_final_truth"]["residual_uncertainty_classification"] == (
        "unresolved_residual_uncertainty"
    )
    assert approval_rows[0]["control_plane_target_final_truth"]["degradation_classification"] == "no_degradation"
    assert approval_rows[0]["control_plane_target_final_truth"]["terminality_basis"] == "completed_terminal"
    assert approval_rows[0]["control_plane_target_final_truth"]["authoritative_result_ref"] == (
        "kernel-execution-result:" + ("2" * 64)
    )
    assert approval_rows[0]["control_plane_target_final_truth"]["authority_sources"] == ["receipt_evidence"]

    event_types = {str(row.get("event_type") or "") for row in list(ledger.json().get("items") or [])}
    assert {
        "projection.issued",
        "proposal.received",
        "admission.decided",
        "approval.requested",
        "approval.decided",
        "commit.recorded",
    }.issubset(event_types)
    assert "action.executed" not in event_types
    assert "action.result_validated" not in event_types

    assert rebuild.json()["count"] == 0
    operator_actions = list(repository.operator_action_by_id.values())
    assert operator_actions
    target_refs = {record.target_ref for record in operator_actions}
    assert f"approval-request:{approval_id}" in target_refs
    assert f"kernel-action-run:{session_id}:{trace_id}" in target_refs

    replay_payload = replay.json()
    assert replay_payload["decision_summary"]["admission_decision"] == "NEEDS_APPROVAL"
    assert replay_payload["decision_summary"]["approval_status"] == "APPROVED"
    assert replay_payload["decision_summary"]["commit_status"] == "COMMITTED"
    assert replay_payload["execution_summary"]["execution_claimed"] is True
    assert replay_payload["execution_summary"]["executed"] is False
    assert replay_payload["execution_summary"]["validated"] is False
    assert replay_payload["execution_summary"]["evidence_status"] == "claimed_only"

    audit_payload = audit.json()
    checks = {str(row.get("check") or ""): bool(row.get("ok")) for row in list(audit_payload.get("checks") or [])}
    assert audit_payload["ok"] is True
    assert checks["approval_path_complete"] is True
    assert checks["execution_path_consistent"] is True
    assert checks["approval_queue_rebuild_consistent"] is True
