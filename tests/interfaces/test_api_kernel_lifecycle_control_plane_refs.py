# Layer: unit

from __future__ import annotations

from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.interfaces.api import app
from orket.core.domain import LeaseStatus, ReservationStatus
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


client = TestClient(app)


def _install_control_plane(monkeypatch) -> tuple[
    InMemoryControlPlaneExecutionRepository,
    InMemoryControlPlaneRecordRepository,
]:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    monkeypatch.setattr(api_module.engine, "control_plane_execution_repository", execution_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", record_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", ControlPlanePublicationService(repository=record_repo))
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane",
        KernelActionControlPlaneService(
            execution_repository=execution_repo,
            publication=api_module.engine.control_plane_publication,
        ),
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_view",
        KernelActionControlPlaneViewService(
            record_repository=record_repo,
            execution_repository=execution_repo,
        ),
    )
    return execution_repo, record_repo


def test_kernel_api_observed_policy_reject_returns_post_effect_recovery_and_lease_refs(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    _install_control_plane(monkeypatch)

    session_id = "sess-real-kernel-cp-reject-observed"
    trace_id = "trace-real-kernel-cp-reject-observed"
    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "execution_result_payload": {"ok": True, "unsafe": True},
            "revalidate_policy_forbidden": True,
        },
    )
    assert committed.status_code == 200
    committed_payload = committed.json()
    assert committed_payload["status"] == "REJECTED_POLICY"
    assert committed_payload["control_plane_attempt_state"] == "attempt_failed"
    assert committed_payload["control_plane_lease_id"].startswith("kernel-action-lease:")
    assert committed_payload["control_plane_resource_id"] == f"kernel-action-scope:session:{session_id}"
    assert committed_payload["control_plane_recovery_decision_id"].startswith("kernel-action-recovery:")
    assert committed_payload["control_plane_recovery_action"] == "terminate_run"

    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert replay.status_code == 200
    control_plane = replay.json()["control_plane"]
    assert control_plane["current_attempt_state"] == "attempt_failed"
    assert control_plane["current_attempt_side_effect_boundary_class"] == "post_effect_observed"
    assert control_plane["latest_lease"]["status"] == "lease_released"
    assert control_plane["latest_resource"]["resource_id"] == f"kernel-action-scope:session:{session_id}"
    assert control_plane["latest_resource"]["current_observed_state"].startswith("lease_status:lease_released;")
    assert control_plane["latest_resource"]["resource_kind"] == "kernel_action_scope"


def test_kernel_api_pre_effect_policy_reject_returns_abandoned_attempt_and_recovery_refs(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    _install_control_plane(monkeypatch)

    session_id = "sess-real-kernel-cp-reject-no-observed"
    trace_id = "trace-real-kernel-cp-reject-no-observed"
    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "revalidate_policy_forbidden": True,
        },
    )
    assert committed.status_code == 200
    committed_payload = committed.json()
    assert committed_payload["status"] == "REJECTED_POLICY"
    assert committed_payload.get("control_plane_lease_id") is None
    assert committed_payload.get("control_plane_resource_id") is None
    assert committed_payload["control_plane_attempt_state"] == "attempt_abandoned"
    assert committed_payload["control_plane_reservation_id"].startswith("kernel-action-reservation:")
    assert committed_payload["control_plane_recovery_decision_id"].startswith("kernel-action-recovery:")
    assert committed_payload["control_plane_recovery_action"] == "terminate_run"

    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert replay.status_code == 200
    control_plane = replay.json()["control_plane"]
    assert control_plane["run_state"] == "failed_terminal"
    assert control_plane["current_attempt_state"] == "attempt_abandoned"
    assert control_plane["current_attempt_side_effect_boundary_class"] == "pre_effect_failure"
    assert control_plane["current_attempt_failure_class"] == "kernel_action_policy_rejected"
    assert control_plane["current_attempt_failure_plane"] == "truth_failure"
    assert control_plane["current_attempt_failure_classification"] == "claim_exceeds_authority"
    assert control_plane["current_recovery_decision_id"].startswith("kernel-action-recovery:")
    assert control_plane["current_recovery_action"] == "terminate_run"
    assert control_plane["latest_lease"] is None
    assert control_plane["latest_resource"] is None
    assert control_plane["latest_reservation"]["status"] == "reservation_released"


def test_kernel_api_commit_fail_closes_authority_on_execution_promotion_failure(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    _execution_repo, record_repo = _install_control_plane(monkeypatch)

    async def _raise_promote_failure(**_kwargs):
        raise RuntimeError("promote failed")

    monkeypatch.setattr(
        api_module.engine.control_plane_publication,
        "promote_reservation_to_lease",
        _raise_promote_failure,
    )

    failure_client = TestClient(app, raise_server_exceptions=False)
    session_id = "sess-real-kernel-cp-promotion-failure"
    trace_id = "trace-real-kernel-cp-promotion-failure"
    admitted = failure_client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()
    run_id = admitted_payload["control_plane_run_id"]

    committed = failure_client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "execution_result_payload": {"ok": True},
        },
    )

    assert committed.status_code == 500
    assert committed.text == "Internal Server Error"
    reservation = record_repo.reservations_by_id[reservation_id_for_run(run_id=run_id)]
    lease = record_repo.leases_by_id[lease_id_for_run(run_id=run_id)]
    assert [record.status for record in reservation] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.INVALIDATED,
    ]
    assert reservation[-1].expiry_or_invalidation_basis == "kernel_action_execution_activation_failed"
    assert [record.status for record in lease] == [
        LeaseStatus.ACTIVE,
        LeaseStatus.RELEASED,
    ]
    assert lease[-1].expiry_basis == "kernel_action_execution_activation_failed"
    resources = record_repo.resources_by_id[f"kernel-action-scope:session:{session_id}"]
    assert [record.current_observed_state.split(";")[0] for record in resources] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]


def test_kernel_api_admit_fails_closed_on_namespace_scope_escalation(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    _install_control_plane(monkeypatch)

    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-real-kernel-cp-namespace-1",
            "trace_id": "trace-real-kernel-cp-namespace-1",
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"tool_name": "write_file", "namespace_scope": "issue:ISSUE-99"},
            },
        },
    )

    assert admitted.status_code == 400
    assert "namespace scope escalation is not permitted" in admitted.json()["detail"]
