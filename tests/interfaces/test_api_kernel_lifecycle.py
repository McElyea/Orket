from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from orket.interfaces.api import app
import orket.interfaces.api as api_module
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


client = TestClient(app)
DEFAULT_COMPARE_FIXTURE_PATH = Path("tests/interfaces/fixtures/kernel_compare_realistic_fixture.json")
CONTRACTS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28/contracts")


def _load_schema(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_registry(root_schema: dict) -> Registry:
    schema_paths = [
        str(CONTRACTS_ROOT / "replay-report.schema.json"),
        str(CONTRACTS_ROOT / "kernel-issue.schema.json"),
    ]
    registry = Registry().with_resource(root_schema["$id"], Resource.from_contents(root_schema))
    for path in schema_paths:
        schema = _load_schema(path)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            registry = registry.with_resource(schema_id, Resource.from_contents(schema))
    return registry


def _load_compare_fixture_payload() -> dict:
    override = os.getenv("ORKET_KERNEL_COMPARE_FIXTURE_PATH")
    fixture_path = Path(override) if override else DEFAULT_COMPARE_FIXTURE_PATH
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_kernel_lifecycle_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_run_lifecycle(*, workflow_id, execute_turn_requests, finish_outcome="PASS", start_request=None):
        captured["workflow_id"] = workflow_id
        captured["execute_turn_requests"] = execute_turn_requests
        captured["finish_outcome"] = finish_outcome
        captured["start_request"] = start_request
        return {"ok": True, "workflow_id": workflow_id}

    monkeypatch.setattr(api_module.engine, "kernel_run_lifecycle", fake_kernel_run_lifecycle)

    response = client.post(
        "/v1/kernel/lifecycle",
        headers={"X-API-Key": "test-key"},
        json={
            "workflow_id": "wf-api-kernel",
            "execute_turn_requests": [{"turn_id": "turn-0001", "turn_input": {}, "commit_intent": "stage_only"}],
            "finish_outcome": "PASS",
            "start_request": {"visibility_mode": "local_only"},
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "workflow_id": "wf-api-kernel"}
    assert captured["workflow_id"] == "wf-api-kernel"
    assert captured["execute_turn_requests"][0]["turn_id"] == "turn-0001"


def test_kernel_compare_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_compare_runs(request):
        captured["request"] = request
        return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_EQUIVALENCE_FAILED"}]}

    monkeypatch.setattr(api_module.engine, "kernel_compare_runs", fake_kernel_compare_runs)

    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a"},
            "run_b": {"run_id": "run-b"},
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "FAIL"
    assert response.json()["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert captured["request"]["contract_version"] == "kernel_api/v1"
    assert captured["request"]["run_a"]["run_id"] == "run-a"


def test_kernel_projection_pack_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    def fake_kernel_projection_pack(request):
        captured["request"] = request
        return {"ok": True, "projection_pack_digest": "a" * 64}

    monkeypatch.setattr(api_module.engine, "kernel_projection_pack", fake_kernel_projection_pack)

    response = client.post(
        "/v1/kernel/projection-pack",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-1",
            "trace_id": "trace-api-1",
            "purpose": "action_path",
            "tool_context_summary": {"tool": "write_file"},
            "policy_context": {"mode": "strict"},
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert captured["request"]["contract_version"] == "kernel_api/v1"
    assert captured["request"]["session_id"] == "sess-api-1"


def test_kernel_admit_proposal_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_kernel_admit_proposal_async(request):
        captured["request"] = request
        return {"proposal_digest": "b" * 64, "admission_decision": {"decision": "ACCEPT_TO_UNIFY"}}

    monkeypatch.setattr(api_module.engine, "kernel_admit_proposal_async", fake_kernel_admit_proposal_async)

    response = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-2",
            "trace_id": "trace-api-2",
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
    )
    assert response.status_code == 200
    assert response.json()["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
    assert captured["request"]["contract_version"] == "kernel_api/v1"


def test_kernel_commit_proposal_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_kernel_commit_proposal_async(request):
        captured["request"] = request
        return {"status": "COMMITTED", "commit_event_digest": "c" * 64}

    monkeypatch.setattr(api_module.engine, "kernel_commit_proposal_async", fake_kernel_commit_proposal_async)

    response = client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-3",
            "trace_id": "trace-api-3",
            "proposal_digest": "d" * 64,
            "admission_decision_digest": "e" * 64,
            "execution_result_digest": "f" * 64,
            "execution_result_payload": {"ok": True},
            "execution_result_schema_valid": True,
            "execution_error_reason_code": "TOKEN_INVALID",
            "canonical_state_digest_after": "1" * 64,
            "block_result_leaks": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMMITTED"
    assert captured["request"]["contract_version"] == "kernel_api/v1"
    assert captured["request"]["execution_result_payload"] == {"ok": True}
    assert captured["request"]["execution_result_schema_valid"] is True
    assert captured["request"]["execution_error_reason_code"] == "TOKEN_INVALID"
    assert captured["request"]["canonical_state_digest_after"] == "1" * 64
    assert captured["request"]["block_result_leaks"] is True


def test_kernel_end_session_endpoint_routes_to_engine(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    captured = {}

    async def fake_kernel_end_session_async(request):
        captured["request"] = request
        return {"status": "ENDED", "event_digest": "1" * 64}

    monkeypatch.setattr(api_module.engine, "kernel_end_session_async", fake_kernel_end_session_async)

    response = client.post(
        "/v1/kernel/end-session",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-api-4",
            "trace_id": "trace-api-4",
            "reason": "manual-close",
            "attestation_scope": "run_scope",
            "attestation_payload": {"operator_note": "confirmed"},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ENDED"
    assert captured["request"]["contract_version"] == "kernel_api/v1"
    assert captured["request"]["attestation_scope"] == "run_scope"
    assert captured["request"]["attestation_payload"] == {"operator_note": "confirmed"}
    assert captured["request"]["operator_actor_ref"].startswith("api_key_fingerprint:sha256:")


def test_kernel_projection_admit_commit_end_session_real_engine_flow(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    session_id = "sess-real-kernel-1"
    trace_id = "trace-real-kernel-1"

    projection = client.post(
        "/v1/kernel/projection-pack",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "purpose": "action_path",
            "tool_context_summary": {"tool": "write_file"},
            "policy_context": {"mode": "strict"},
        },
    )
    assert projection.status_code == 200
    projection_payload = projection.json()
    assert projection_payload["contract_version"] == "kernel_api/v1"
    assert projection_payload["canonical_state_digest"] == "0" * 64

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
    assert admitted_payload["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "execution_result_digest": "a" * 64,
        },
    )
    assert committed.status_code == 200
    commit_payload = committed.json()
    assert commit_payload["status"] == "COMMITTED"
    assert isinstance(commit_payload["commit_event_digest"], str) and len(commit_payload["commit_event_digest"]) == 64

    ended = client.post(
        "/v1/kernel/end-session",
        headers={"X-API-Key": "test-key"},
        json={"session_id": session_id, "trace_id": trace_id, "reason": "done"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ENDED"


def test_kernel_api_real_engine_flow_publishes_control_plane_governed_action_truth(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
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

    session_id = "sess-real-kernel-cp-1"
    trace_id = "trace-real-kernel-cp-1"
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
    assert admitted_payload["control_plane_reservation_id"].startswith("kernel-action-reservation:")

    committed = client.post(
        "/v1/kernel/commit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": admitted_payload["proposal_digest"],
            "admission_decision_digest": admitted_payload["decision_digest"],
            "execution_result_digest": "f" * 64,
            "execution_result_payload": {"ok": True, "path": "workspace/out.txt"},
            "execution_result_schema_valid": True,
        },
    )
    assert committed.status_code == 200
    assert committed.json()["status"] == "COMMITTED"
    assert committed.json()["control_plane_run_id"].startswith("kernel-action-run:")
    assert committed.json()["control_plane_attempt_id"].startswith("kernel-action-attempt:")
    assert committed.json()["control_plane_attempt_state"] == "attempt_completed"
    assert committed.json()["control_plane_reservation_id"].startswith("kernel-action-reservation:")
    assert committed.json()["control_plane_lease_id"].startswith("kernel-action-lease:")
    assert committed.json()["control_plane_resource_id"] == f"kernel-action-scope:session:{session_id}"
    assert committed.json()["control_plane_final_truth_record_id"].startswith("kernel-action-final-truth:")

    run = execution_repo.run_by_id[KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)]
    attempt = execution_repo.attempt_by_id[
        KernelActionControlPlaneService.attempt_id_for(session_id=session_id, trace_id=trace_id)
    ]
    final_truth = record_repo.final_truth_by_run[run.run_id]
    effects = record_repo.journal_by_run[run.run_id]

    assert run.lifecycle_state.value == "completed"
    assert attempt.attempt_state.value == "attempt_completed"
    assert len(execution_repo.step_by_id) == 1
    assert final_truth.result_class.value == "success"
    assert len(effects) == 1

    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert replay.status_code == 200
    assert replay.json()["control_plane"]["run_state"] == "completed"
    assert replay.json()["control_plane"]["step_count"] == 1
    assert replay.json()["control_plane"]["effect_entry_count"] == 1
    reservation = replay.json()["control_plane"]["latest_reservation"]
    assert reservation is not None
    assert reservation["reservation_kind"] == "concurrency_reservation"
    assert reservation["status"] == "reservation_promoted_to_lease"
    assert reservation["expiry_or_invalidation_basis"] == "kernel_action_execution_started"
    assert replay.json()["control_plane"]["latest_lease"]["status"] == "lease_released"
    assert replay.json()["control_plane"]["latest_step"]["namespace_scope"] == f"session:{session_id}"
    assert replay.json()["control_plane"]["latest_step"]["resources_touched"] == [
        f"kernel-action-target:{session_id}:{trace_id}"
    ]
    assert replay.json()["control_plane"]["latest_step"]["receipt_refs"]
    assert replay.json()["control_plane"]["final_truth"]["result_class"] == "success"
    assert replay.json()["control_plane"]["final_truth"]["evidence_sufficiency_classification"] == (
        "evidence_sufficient"
    )
    assert replay.json()["control_plane"]["final_truth"]["residual_uncertainty_classification"] == (
        "no_residual_uncertainty"
    )
    assert replay.json()["control_plane"]["final_truth"]["degradation_classification"] == "no_degradation"
    assert replay.json()["control_plane"]["final_truth"]["terminality_basis"] == "completed_terminal"
    assert replay.json()["control_plane"]["final_truth"]["authoritative_result_ref"] == (
        "kernel-execution-result:" + ("f" * 64)
    )
    assert replay.json()["control_plane"]["final_truth"]["authority_sources"] == [
        "receipt_evidence",
        "validated_artifact",
    ]


def test_kernel_api_replay_exposes_active_reservation_for_needs_approval_trace(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
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

    session_id = "sess-real-kernel-cp-approval-1"
    trace_id = "trace-real-kernel-cp-approval-1"
    admitted = client.post(
        "/v1/kernel/admit-proposal",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        },
    )
    assert admitted.status_code == 200
    admitted_payload = admitted.json()
    assert admitted_payload["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert admitted_payload["approval_id"]
    assert admitted_payload["control_plane_reservation_id"].startswith("approval-reservation:")

    replay = client.get(
        "/v1/kernel/action-lifecycle/replay",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert replay.status_code == 200
    control_plane = replay.json()["control_plane"]
    assert control_plane["run_state"] == "admitted"
    assert control_plane["current_attempt_state"] == "attempt_created"
    assert control_plane["latest_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert control_plane["latest_reservation"]["status"] == "reservation_active"
    assert control_plane["latest_reservation"]["expiry_or_invalidation_basis"] == (
        "pending_tool_approval:action.tool_call"
    )
    assert control_plane["latest_reservation"]["supervisor_authority_ref"] == (
        f"tool-approval-gate:{admitted_payload['approval_id']}:create"
    )
    assert control_plane["latest_lease"] is None


def test_kernel_api_end_session_publishes_operator_cancel_for_unfinished_trace(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_execution_repository", execution_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", record_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication)
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane",
        KernelActionControlPlaneService(
            execution_repository=execution_repo,
            publication=publication,
        ),
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_operator",
        KernelActionControlPlaneOperatorService(publication=publication),
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_view",
        KernelActionControlPlaneViewService(
            record_repository=record_repo,
            execution_repository=execution_repo,
        ),
    )

    session_id = "sess-real-kernel-cp-cancel"
    trace_id = "trace-real-kernel-cp-cancel"
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

    ended = client.post(
        "/v1/kernel/end-session",
        headers={"X-API-Key": "test-key"},
        json={"session_id": session_id, "trace_id": trace_id, "reason": "manual-close"},
    )
    assert ended.status_code == 200
    assert ended.json()["control_plane_run_id"].startswith("kernel-action-run:")
    assert ended.json()["control_plane_final_truth_record_id"].startswith("kernel-action-final-truth:")
    assert ended.json()["control_plane_operator_action_id"].startswith("kernel-action-operator:")
    run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
    actions = [record for record in record_repo.operator_action_by_id.values() if record.target_ref == run_id]
    assert len(actions) == 1
    assert actions[0].command_class.value == "cancel_run"

    audit = client.get(
        "/v1/kernel/action-lifecycle/audit",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert audit.status_code == 200
    assert audit.json()["control_plane"]["latest_operator_action"]["command_class"] == "cancel_run"
    assert audit.json()["control_plane"]["latest_operator_action"]["receipt_refs"] == [
        f"kernel-ledger-event:{ended.json()['event_digest']}"
    ]
    assert audit.json()["control_plane"]["latest_operator_action"]["affected_transition_refs"] == [
        f"kernel-action-run:{session_id}:{trace_id}"
    ]
    assert audit.json()["control_plane"]["latest_operator_action"]["affected_resource_refs"] == [
        f"kernel-action-scope:session:{session_id}"
    ]


def test_kernel_api_end_session_publishes_attestation_when_requested(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_execution_repository", execution_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_repository", record_repo)
    monkeypatch.setattr(api_module.engine, "control_plane_publication", publication)
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane",
        KernelActionControlPlaneService(
            execution_repository=execution_repo,
            publication=publication,
        ),
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_operator",
        KernelActionControlPlaneOperatorService(publication=publication),
    )
    monkeypatch.setattr(
        api_module.engine,
        "kernel_action_control_plane_view",
        KernelActionControlPlaneViewService(
            record_repository=record_repo,
            execution_repository=execution_repo,
        ),
    )

    session_id = "sess-real-kernel-cp-attestation"
    trace_id = "trace-real-kernel-cp-attestation"
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

    ended = client.post(
        "/v1/kernel/end-session",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": session_id,
            "trace_id": trace_id,
            "reason": "manual-close",
            "attestation_scope": "run_scope",
            "attestation_payload": {"operator_note": "manual_state_check"},
            "request_id": "req-kernel-attestation-1",
        },
    )
    assert ended.status_code == 200
    run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
    actions = [record for record in record_repo.operator_action_by_id.values() if record.target_ref == run_id]
    assert len(actions) == 2
    input_classes = sorted(record.input_class.value for record in actions)
    assert input_classes == ["operator_attestation", "operator_command"]
    attestation = next(record for record in actions if record.input_class.value == "operator_attestation")
    assert attestation.attestation_scope == "run_scope"
    assert attestation.attestation_payload == {"operator_note": "manual_state_check"}

    audit = client.get(
        "/v1/kernel/action-lifecycle/audit",
        headers={"X-API-Key": "test-key"},
        params={"session_id": session_id, "trace_id": trace_id},
    )
    assert audit.status_code == 200
    assert audit.json()["control_plane"]["latest_operator_action"]["input_class"] == "operator_attestation"
    assert audit.json()["control_plane"]["latest_operator_action"]["attestation_scope"] == "run_scope"
    assert audit.json()["control_plane"]["latest_operator_action"]["attestation_payload"] == {
        "operator_note": "manual_state_check"
    }
    assert audit.json()["control_plane"]["latest_operator_action"]["affected_transition_refs"] == [
        f"kernel-action-run:{session_id}:{trace_id}"
    ]
    assert audit.json()["control_plane"]["latest_operator_action"]["affected_resource_refs"] == [
        f"kernel-action-scope:session:{session_id}"
    ]


def test_kernel_projection_pack_returns_400_when_nervous_system_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)

    response = client.post(
        "/v1/kernel/projection-pack",
        headers={"X-API-Key": "test-key"},
        json={
            "session_id": "sess-real-kernel-flag-off",
            "trace_id": "trace-real-kernel-flag-off",
            "purpose": "action_path",
            "tool_context_summary": {},
            "policy_context": {},
        },
    )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


def test_kernel_replay_endpoint_routes_to_engine_and_propagates_failure_codes(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    def fake_kernel_replay_run(request):
        descriptor = request.get("run_descriptor", {})
        if "workflow_id" not in descriptor:
            return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_INPUT_MISSING"}]}
        if descriptor.get("contract_version") != "kernel_api/v1":
            return {"outcome": "FAIL", "issues": [{"code": "E_REPLAY_VERSION_MISMATCH"}]}
        return {"outcome": "PASS", "issues": []}

    monkeypatch.setattr(api_module.engine, "kernel_replay_run", fake_kernel_replay_run)

    missing = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={"run_descriptor": {"run_id": "run-r1"}},
    )
    assert missing.status_code == 200
    assert missing.json()["issues"][0]["code"] == "E_REPLAY_INPUT_MISSING"

    mismatch = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={
            "run_descriptor": {
                "run_id": "run-r2",
                "workflow_id": "wf-r2",
                "contract_version": "kernel_api/v0",
                "schema_version": "v1",
            }
        },
    )
    assert mismatch.status_code == 200
    assert mismatch.json()["issues"][0]["code"] == "E_REPLAY_VERSION_MISMATCH"


def test_kernel_replay_endpoint_real_engine_success_with_full_descriptor(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={
            "run_descriptor": {
                "run_id": "run-r3",
                "workflow_id": "wf-r3",
                "policy_profile_ref": "policy:v1",
                "model_profile_ref": "model:v1",
                "runtime_profile_ref": "runtime:v1",
                "trace_ref": "trace://run-r3",
                "state_ref": "state://run-r3",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "PASS"
    assert payload["mode"] == "replay_run"
    schema = _load_schema(str(CONTRACTS_ROOT / "replay-report.schema.json"))
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(payload)


def test_kernel_replay_endpoint_real_engine_fail_payload_conforms_schema(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/replay",
        headers={"X-API-Key": "test-key"},
        json={"run_descriptor": {"run_id": "run-r4"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_INPUT_MISSING"
    schema = _load_schema(str(CONTRACTS_ROOT / "replay-report.schema.json"))
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(payload)


def test_kernel_compare_endpoint_real_engine_detects_pointer_drift(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "orphan",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/1",
                        "message": "orphan",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["issue_codes"]


def test_kernel_compare_endpoint_real_engine_contract_version_drift(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v0",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["contract_version"]


def test_kernel_compare_endpoint_real_engine_pointer_and_stage_drift_ordering(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "x",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "FAIL"}],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/1",
                        "message": "y",
                        "details": {},
                    }
                ],
                "events": [],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "FAIL"
    assert payload["issues"][0]["code"] == "E_REPLAY_EQUIVALENCE_FAILED"
    assert payload["issues"][0]["details"]["mismatch_fields"] == ["issue_codes", "stage_outcomes"]


def test_kernel_compare_endpoint_real_engine_passes_mixed_order_normalization(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {
                "run_id": "run-a",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "promotion",
                        "code": "E_PROMOTION_OUT_OF_ORDER",
                        "location": "/turns/2",
                        "message": "x",
                        "details": {},
                    },
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "y",
                        "details": {},
                    },
                ],
                "events": [
                    "[INFO] [STAGE:promotion] [CODE:I_NOOP_PROMOTION] [LOC:/turn-0002] noop |",
                    "[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass |",
                ],
            },
            "run_b": {
                "run_id": "run-b",
                "contract_version": "kernel_api/v1",
                "schema_version": "v1",
                "turn_digests": [],
                "stage_outcomes": [],
                "issues": [
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "lsi",
                        "code": "E_LSI_ORPHAN_TARGET",
                        "location": "/links/declares/0",
                        "message": "different",
                        "details": {},
                    },
                    {
                        "contract_version": "kernel_api/v1",
                        "level": "FAIL",
                        "stage": "promotion",
                        "code": "E_PROMOTION_OUT_OF_ORDER",
                        "location": "/turns/2",
                        "message": "different",
                        "details": {},
                    },
                ],
                "events": [
                    "[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] pass alt |",
                    "[INFO] [STAGE:promotion] [CODE:I_NOOP_PROMOTION] [LOC:/turn-0002] noop alt |",
                ],
            },
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "PASS"


def test_kernel_compare_endpoint_response_conforms_to_replay_report_schema(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a", "contract_version": "kernel_api/v1", "schema_version": "v1", "turn_digests": [], "stage_outcomes": [], "issues": [], "events": []},
            "run_b": {"run_id": "run-b", "contract_version": "kernel_api/v1", "schema_version": "v1", "turn_digests": [], "stage_outcomes": [], "issues": [], "events": []},
            "compare_mode": "structural_parity",
        },
    )
    assert response.status_code == 200
    schema = _load_schema(str(CONTRACTS_ROOT / "replay-report.schema.json"))
    registry = _build_registry(schema)
    Draft202012Validator(schema, registry=registry).validate(response.json())


def test_kernel_compare_endpoint_malformed_payload_rejected(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": {"run_id": "run-a"},
            "compare_mode": "structural_parity"
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"][0]["loc"][-1] == "run_b"


def test_kernel_compare_endpoint_realistic_artifact_fixture(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    fixture = _load_compare_fixture_payload()

    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": fixture["run_a"],
            "run_b": fixture["run_b"],
            "compare_mode": fixture["compare_mode"],
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == fixture["expect_outcome"]


def test_kernel_compare_endpoint_generated_fixture_optional_parity_source(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    generated_fixture = tmp_path / "kernel_compare_generated_fixture.json"
    result = subprocess.run(
        [sys.executable, "scripts/governance/gen_kernel_compare_fixture.py", "--out", str(generated_fixture)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    monkeypatch.setenv("ORKET_KERNEL_COMPARE_FIXTURE_PATH", str(generated_fixture))

    fixture = _load_compare_fixture_payload()
    response = client.post(
        "/v1/kernel/compare",
        headers={"X-API-Key": "test-key"},
        json={
            "run_a": fixture["run_a"],
            "run_b": fixture["run_b"],
            "compare_mode": fixture["compare_mode"],
        },
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == fixture["expect_outcome"]
