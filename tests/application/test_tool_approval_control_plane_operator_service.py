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
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_tool_approval_operator_service_publishes_risk_acceptance_for_approved_edit() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    action = await service.publish_granted_approval_risk_acceptance(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={
            "approval_id": "apr-1",
            "status": "PENDING",
        },
        resolved_approval={
            "approval_id": "apr-1",
            "session_id": "sess-1",
            "issue_id": "ISS-1",
            "gate_mode": "approval_required",
            "request_type": "tool_approval",
            "reason": "approval_required_tool:write_file",
            "status": "APPROVED_WITH_EDITS",
            "resolution": {
                "decision": "edit",
            },
            "updated_at": "2026-03-24T02:10:00+00:00",
        },
    )

    stored = await repository.get_operator_action(action_id=action.action_id)

    assert stored is not None
    assert stored.input_class is OperatorInputClass.RISK_ACCEPTANCE
    assert stored.target_ref == "approval-request:apr-1"
    assert stored.result == "approved_with_edits"
    assert stored.risk_acceptance_scope is not None
    assert "decision=edit" in stored.risk_acceptance_scope


@pytest.mark.asyncio
async def test_tool_approval_operator_service_publishes_terminal_command_for_denial() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    action = await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={
            "approval_id": "apr-2",
            "status": "PENDING",
        },
        resolved_approval={
            "approval_id": "apr-2",
            "session_id": "sess-2",
            "issue_id": "ISS-2",
            "request_type": "tool_approval",
            "reason": "approval_required_tool:write_file",
            "status": "DENIED",
            "resolution": {
                "decision": "deny",
            },
            "updated_at": "2026-03-24T02:11:00+00:00",
        },
    )

    stored = await repository.get_operator_action(action_id=action.action_id)

    assert stored is not None
    assert stored.input_class is OperatorInputClass.COMMAND
    assert stored.command_class is OperatorCommandClass.MARK_TERMINAL
    assert stored.target_ref == "approval-request:apr-2"
    assert stored.result == "denied"


@pytest.mark.asyncio
async def test_tool_approval_operator_service_publishes_secondary_action_for_control_plane_run_target() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={
            "approval_id": "apr-3",
            "status": "PENDING",
        },
        resolved_approval={
            "approval_id": "apr-3",
            "session_id": "sess-3",
            "issue_id": "ISS-3",
            "gate_mode": "approval_required",
            "request_type": "tool_approval",
            "reason": "approval_required_tool:write_file",
            "payload": {
                "control_plane_target_ref": "turn-tool-run:sess-3:ISS-3:coder:0001",
            },
            "status": "APPROVED",
            "resolution": {
                "decision": "approve",
            },
            "updated_at": "2026-03-24T02:12:00+00:00",
        },
    )

    approval_actions = await repository.list_operator_actions(target_ref="approval-request:apr-3")
    run_actions = await repository.list_operator_actions(target_ref="turn-tool-run:sess-3:ISS-3:coder:0001")

    assert len(approval_actions) == 1
    assert len(run_actions) == 1
    assert run_actions[0].input_class is OperatorInputClass.RISK_ACCEPTANCE
    assert run_actions[0].receipt_refs == ["approval-request:apr-3"]


@pytest.mark.asyncio
async def test_tool_approval_operator_service_falls_back_to_reservation_target_when_payload_omits_it() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=repository)
    reservations = ToolApprovalControlPlaneReservationService(publication=publication)
    service = ToolApprovalControlPlaneOperatorService(publication=publication)

    await reservations.publish_pending_tool_approval_hold(
        approval_id="apr-4",
        session_id="sess-4",
        issue_id="",
        seat_name="kernel_action",
        tool_name="action.tool_call",
        turn_index=None,
        created_at="2026-03-24T02:13:00+00:00",
        control_plane_target_ref="kernel-action-run:sess-4:trace-4",
    )

    await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={
            "approval_id": "apr-4",
            "status": "PENDING",
        },
        resolved_approval={
            "approval_id": "apr-4",
            "session_id": "sess-4",
            "gate_mode": "approval_required",
            "request_type": "tool_approval",
            "reason": "approval_required_tool:action.tool_call",
            "status": "APPROVED",
            "resolution": {
                "decision": "approve",
            },
            "updated_at": "2026-03-24T02:14:00+00:00",
        },
    )

    approval_actions = await repository.list_operator_actions(target_ref="approval-request:apr-4")
    run_actions = await repository.list_operator_actions(target_ref="kernel-action-run:sess-4:trace-4")

    assert len(approval_actions) == 1
    assert len(run_actions) == 1
    assert run_actions[0].input_class is OperatorInputClass.RISK_ACCEPTANCE
    assert run_actions[0].receipt_refs == ["approval-request:apr-4"]
