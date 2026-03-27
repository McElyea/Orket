# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_kernel_action_control_plane_view_service_summarizes_run_effect_and_operator_state() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    control_plane = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )
    operator = KernelActionControlPlaneOperatorService(publication=publication)
    reservations = ToolApprovalControlPlaneReservationService(publication=publication)
    view = KernelActionControlPlaneViewService(
        record_repository=record_repo,
        execution_repository=execution_repo,
    )

    session_id = "sess-kernel-view-1"
    trace_id = "trace-kernel-view-1"
    await control_plane.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "1" * 64,
            "decision_digest": "2" * 64,
            "event_digest": "3" * 64,
        },
        ledger_items=[
            {"event_type": "admission.decided", "created_at": "2026-03-24T13:00:00+00:00", "event_digest": "3" * 64}
        ],
    )
    await reservations.publish_pending_tool_approval_hold(
        approval_id="approval-kernel-view-1",
        session_id=session_id,
        issue_id="",
        seat_name="kernel_action",
        tool_name="write_file",
        turn_index=None,
        created_at="2026-03-24T13:00:00+00:00",
        control_plane_target_ref=KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id),
    )
    await control_plane.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": "1" * 64,
            "admission_decision_digest": "2" * 64,
            "execution_result_digest": "4" * 64,
            "execution_result_payload": {"ok": True},
        },
        response={"status": "COMMITTED", "commit_event_digest": "5" * 64},
        ledger_items=[
            {"event_type": "action.executed", "created_at": "2026-03-24T13:00:01+00:00", "event_digest": "6" * 64},
            {
                "event_type": "action.result_validated",
                "created_at": "2026-03-24T13:00:02+00:00",
                "event_digest": "7" * 64,
            },
            {"event_type": "commit.recorded", "created_at": "2026-03-24T13:00:03+00:00", "event_digest": "5" * 64},
        ],
    )
    await operator.publish_cancel_run_command(
        actor_ref="api_key_fingerprint:sha256:test",
        session_id=session_id,
        trace_id=trace_id,
        timestamp="2026-03-24T13:00:04+00:00",
        receipt_ref="kernel-ledger-event:8",
        reason="manual-close",
    )

    summary = await view.build_summary(session_id=session_id, trace_id=trace_id)

    assert summary is not None
    assert summary["run_state"] == "completed"
    assert summary["current_attempt_state"] == "attempt_completed"
    assert summary["latest_reservation"]["reservation_kind"] == "concurrency_reservation"
    assert summary["latest_reservation"]["status"] == "reservation_promoted_to_lease"
    assert summary["latest_reservation"]["expiry_or_invalidation_basis"] == "kernel_action_execution_started"
    assert summary["latest_reservation"]["supervisor_authority_ref"].endswith(":promote_execution_lease")
    assert summary["latest_lease"]["status"] == "lease_released"
    assert summary["latest_lease"]["expiry_basis"] == "kernel_action_commit_terminal:committed"
    assert summary["step_count"] == 1
    assert summary["latest_step"]["step_kind"] == "governed_kernel_commit_execution"
    assert summary["latest_step"]["namespace_scope"] == f"session:{session_id}"
    assert summary["latest_step"]["closure_classification"] == "step_completed"
    assert summary["latest_step"]["resources_touched"] == [f"kernel-action-target:{session_id}:{trace_id}"]
    assert summary["latest_step"]["receipt_refs"] == [
        "kernel-ledger-event:" + ("6" * 64),
        "kernel-ledger-event:" + ("7" * 64),
        "kernel-ledger-event:" + ("5" * 64),
    ]
    assert summary["effect_entry_count"] == 1
    assert summary["final_truth"]["result_class"] == "success"
    assert summary["final_truth"]["evidence_sufficiency_classification"] == "evidence_sufficient"
    assert summary["final_truth"]["residual_uncertainty_classification"] == "no_residual_uncertainty"
    assert summary["final_truth"]["degradation_classification"] == "no_degradation"
    assert summary["final_truth"]["terminality_basis"] == "completed_terminal"
    assert summary["final_truth"]["authoritative_result_ref"] == "kernel-execution-result:" + ("4" * 64)
    assert summary["final_truth"]["authority_sources"] == ["receipt_evidence", "validated_artifact"]
    assert summary["latest_operator_action"]["command_class"] == "cancel_run"
    assert summary["latest_operator_action"]["risk_acceptance_scope"] is None
    assert summary["latest_operator_action"]["attestation_scope"] is None
    assert summary["latest_operator_action"]["attestation_payload"] == {}
    assert summary["latest_operator_action"]["precondition_basis_ref"] == "kernel-session-end:manual-close"
    assert summary["latest_operator_action"]["receipt_refs"] == ["kernel-ledger-event:8"]
    assert summary["latest_operator_action"]["affected_transition_refs"] == [
        f"kernel-action-run:{session_id}:{trace_id}"
    ]
    assert summary["latest_operator_action"]["affected_resource_refs"] == [
        f"kernel-action-scope:session:{session_id}"
    ]


@pytest.mark.asyncio
async def test_kernel_action_control_plane_view_service_exposes_run_owned_reservation_when_no_pending_gate_hold() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    control_plane = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )
    view = KernelActionControlPlaneViewService(
        record_repository=record_repo,
        execution_repository=execution_repo,
    )

    session_id = "sess-kernel-view-2"
    trace_id = "trace-kernel-view-2"
    await control_plane.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "a" * 64,
            "decision_digest": "b" * 64,
            "event_digest": "c" * 64,
        },
        ledger_items=[
            {"event_type": "admission.decided", "created_at": "2026-03-25T14:00:00+00:00", "event_digest": "c" * 64}
        ],
    )

    summary = await view.build_summary(session_id=session_id, trace_id=trace_id)

    assert summary is not None
    assert summary["run_state"] == "admitted"
    assert summary["latest_reservation"] is not None
    assert summary["latest_reservation"]["reservation_kind"] == "concurrency_reservation"
    assert summary["latest_reservation"]["status"] == "reservation_active"
    assert summary["latest_reservation"]["supervisor_authority_ref"].endswith(":admit")
    assert summary["latest_lease"] is None


@pytest.mark.asyncio
async def test_kernel_action_control_plane_view_service_prefers_run_owned_reservation_after_hold_is_released() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    control_plane = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )
    reservations = ToolApprovalControlPlaneReservationService(publication=publication)
    view = KernelActionControlPlaneViewService(
        record_repository=record_repo,
        execution_repository=execution_repo,
    )

    session_id = "sess-kernel-view-3"
    trace_id = "trace-kernel-view-3"
    run_id = KernelActionControlPlaneService.run_id_for(session_id=session_id, trace_id=trace_id)
    await control_plane.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "1" * 64,
            "decision_digest": "2" * 64,
            "event_digest": "3" * 64,
            "admission_decision": {"decision": "ACCEPT_TO_UNIFY"},
        },
        ledger_items=[
            {"event_type": "admission.decided", "created_at": "2026-03-25T15:00:00+00:00", "event_digest": "3" * 64}
        ],
    )
    await reservations.publish_pending_tool_approval_hold(
        approval_id="approval-kernel-view-3",
        session_id=session_id,
        issue_id="",
        seat_name="kernel_action",
        tool_name="write_file",
        turn_index=None,
        created_at="2026-03-25T15:00:00+00:00",
        control_plane_target_ref=run_id,
    )
    await reservations.publish_resolved_pending_gate_hold(
        resolved_approval={
            "approval_id": "approval-kernel-view-3",
            "request_type": "tool_approval",
            "status": "approved",
        }
    )
    await control_plane.record_commit(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal_digest": "1" * 64,
            "admission_decision_digest": "2" * 64,
            "execution_result_digest": "4" * 64,
            "execution_result_payload": {"ok": True},
        },
        response={"status": "COMMITTED", "commit_event_digest": "5" * 64},
        ledger_items=[
            {"event_type": "action.executed", "created_at": "2026-03-25T15:00:01+00:00", "event_digest": "6" * 64},
            {"event_type": "commit.recorded", "created_at": "2026-03-25T15:00:02+00:00", "event_digest": "5" * 64},
        ],
    )

    summary = await view.build_summary(session_id=session_id, trace_id=trace_id)

    assert summary is not None
    assert summary["latest_reservation"] is not None
    assert summary["latest_reservation"]["reservation_id"].startswith("kernel-action-reservation:")
    assert summary["latest_reservation"]["status"] == "reservation_promoted_to_lease"


@pytest.mark.asyncio
async def test_kernel_action_control_plane_view_service_surfaces_latest_attestation_when_present() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    control_plane = KernelActionControlPlaneService(
        execution_repository=execution_repo,
        publication=publication,
    )
    operator = KernelActionControlPlaneOperatorService(publication=publication)
    view = KernelActionControlPlaneViewService(
        record_repository=record_repo,
        execution_repository=execution_repo,
    )

    session_id = "sess-kernel-view-attestation-1"
    trace_id = "trace-kernel-view-attestation-1"
    await control_plane.record_admission(
        request={
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        },
        response={
            "proposal_digest": "1" * 64,
            "decision_digest": "2" * 64,
            "event_digest": "3" * 64,
        },
        ledger_items=[
            {"event_type": "admission.decided", "created_at": "2026-03-26T14:00:00+00:00", "event_digest": "3" * 64}
        ],
    )
    await operator.publish_cancel_run_command(
        actor_ref="api_key_fingerprint:sha256:test",
        session_id=session_id,
        trace_id=trace_id,
        timestamp="2026-03-26T14:00:01+00:00",
        receipt_ref="kernel-ledger-event:9",
        reason="manual-close",
    )
    await operator.publish_run_attestation(
        actor_ref="api_key_fingerprint:sha256:test",
        session_id=session_id,
        trace_id=trace_id,
        timestamp="2026-03-26T14:00:02+00:00",
        receipt_ref="kernel-ledger-event:9",
        attestation_scope="run_scope",
        attestation_payload={"checkpoint_verified": True},
        request_id="req-attestation-view-1",
    )

    summary = await view.build_summary(session_id=session_id, trace_id=trace_id)

    assert summary is not None
    assert summary["latest_operator_action"]["input_class"] == "operator_attestation"
    assert summary["latest_operator_action"]["command_class"] is None
    assert summary["latest_operator_action"]["risk_acceptance_scope"] is None
    assert summary["latest_operator_action"]["attestation_scope"] == "run_scope"
    assert summary["latest_operator_action"]["attestation_payload"] == {"checkpoint_verified": True}
    assert summary["latest_operator_action"]["affected_transition_refs"] == [
        f"kernel-action-run:{session_id}:{trace_id}"
    ]
    assert summary["latest_operator_action"]["affected_resource_refs"] == [
        f"kernel-action-scope:session:{session_id}"
    ]
