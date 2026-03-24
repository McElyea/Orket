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
    assert summary["latest_reservation"]["reservation_kind"] == "operator_hold_reservation"
    assert summary["latest_reservation"]["status"] == "reservation_active"
    assert summary["latest_reservation"]["expiry_or_invalidation_basis"] == "pending_tool_approval:write_file"
    assert summary["latest_reservation"]["supervisor_authority_ref"] == "tool-approval-gate:approval-kernel-view-1:create"
    assert summary["step_count"] == 1
    assert summary["latest_step"]["step_kind"] == "governed_kernel_commit_execution"
    assert summary["latest_step"]["namespace_scope"] is None
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
    assert summary["latest_operator_action"]["receipt_refs"] == ["kernel-ledger-event:8"]
