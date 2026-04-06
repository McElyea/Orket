# Layer: contract

from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.interfaces.api import app

client = TestClient(app)


def test_sandbox_operator_list_exposes_required_lifecycle_fields(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_get_sandboxes():
        return [
            {
                "sandbox_id": "sb-1",
                "compose_project": "orket-sandbox-sb-1",
                "state": "active",
                "cleanup_state": "none",
                "terminal_reason": None,
                "owner_instance_id": "runner-a",
                "cleanup_owner_instance_id": None,
                "lease_expires_at": "2026-03-11T00:05:00+00:00",
                "heartbeat_age_seconds": 12,
                "restart_summary": {},
                "cleanup_eligible": False,
                "cleanup_due_at": None,
                "requires_reconciliation": False,
                "control_plane_run_state": "executing",
                "control_plane_current_attempt_id": "sandbox-attempt:sb-1:00000001",
                "control_plane_current_attempt_state": "attempt_executing",
                "control_plane_recovery_decision_id": None,
                "control_plane_checkpoint_id": None,
                "control_plane_checkpoint_resumability_class": None,
                "control_plane_checkpoint_acceptance_outcome": None,
                "control_plane_reconciliation_id": None,
                "control_plane_divergence_class": None,
                "control_plane_safe_continuation_class": None,
                "control_plane_reservation_status": "reservation_promoted_to_lease",
                "control_plane_lease_status": "lease_active",
                "final_truth_record_id": None,
                "control_plane_final_result_class": None,
                "control_plane_final_closure_basis": None,
                "control_plane_final_terminality_basis": None,
                "control_plane_final_evidence_sufficiency_class": None,
                "control_plane_final_residual_uncertainty_class": None,
                "control_plane_final_degradation_class": None,
                "control_plane_final_authoritative_result_ref": None,
                "control_plane_final_authority_sources": [],
                "effect_journal_entry_count": 0,
                "latest_effect_journal_entry_id": None,
                "latest_effect_id": None,
                "latest_effect_intended_target_ref": None,
                "latest_effect_observed_result_ref": None,
                "latest_effect_authorization_basis_ref": None,
                "latest_effect_integrity_verification_ref": None,
                "latest_effect_uncertainty_classification": None,
                "operator_action_count": 0,
                "latest_operator_action": None,
            }
        ]

    monkeypatch.setattr(api_module.engine, "get_sandboxes", fake_get_sandboxes)

    response = client.get("/v1/sandboxes", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    body = response.json()
    assert body[0]["sandbox_id"] == "sb-1"
    assert sorted(body[0].keys()) == sorted(
        [
            "sandbox_id",
            "compose_project",
            "state",
            "cleanup_state",
            "terminal_reason",
            "owner_instance_id",
            "cleanup_owner_instance_id",
            "lease_expires_at",
            "heartbeat_age_seconds",
            "restart_summary",
            "cleanup_eligible",
            "cleanup_due_at",
            "requires_reconciliation",
            "control_plane_run_state",
            "control_plane_current_attempt_id",
            "control_plane_current_attempt_state",
            "control_plane_recovery_decision_id",
            "control_plane_checkpoint_id",
            "control_plane_checkpoint_resumability_class",
            "control_plane_checkpoint_acceptance_outcome",
            "control_plane_reconciliation_id",
            "control_plane_divergence_class",
            "control_plane_safe_continuation_class",
            "control_plane_reservation_status",
            "control_plane_lease_status",
            "final_truth_record_id",
            "control_plane_final_result_class",
            "control_plane_final_closure_basis",
            "control_plane_final_terminality_basis",
            "control_plane_final_evidence_sufficiency_class",
            "control_plane_final_residual_uncertainty_class",
            "control_plane_final_degradation_class",
            "control_plane_final_authoritative_result_ref",
            "control_plane_final_authority_sources",
            "effect_journal_entry_count",
            "latest_effect_journal_entry_id",
            "latest_effect_id",
            "latest_effect_intended_target_ref",
            "latest_effect_observed_result_ref",
            "latest_effect_authorization_basis_ref",
            "latest_effect_integrity_verification_ref",
            "latest_effect_uncertainty_classification",
            "operator_action_count",
            "latest_operator_action",
        ]
    )


def test_sandbox_operator_stop_returns_conflict_when_reconciliation_blocked(monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def fake_stop_sandbox(_sandbox_id, *, operator_actor_ref=None):
        assert operator_actor_ref == f"api_key_fingerprint:sha256:{hashlib.sha256(b'test-key').hexdigest()}"
        raise ValueError("Sandbox sb-2 is blocked by requires_reconciliation=true")

    monkeypatch.setattr(api_module.engine, "stop_sandbox", fake_stop_sandbox)
    monkeypatch.setattr(
        api_module.api_runtime_node,
        "resolve_sandbox_stop_invocation",
        lambda sandbox_id: {"method_name": "stop_sandbox", "args": [sandbox_id]},
    )

    response = client.post("/v1/sandboxes/sb-2/stop", headers={"X-API-Key": "test-key"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Sandbox sb-2 is blocked by requires_reconciliation=true"
