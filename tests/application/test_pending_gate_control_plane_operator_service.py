# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.pending_gate_control_plane_operator_service import (
    PendingGateControlPlaneOperatorService,
)
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_pending_gate_operator_service_publishes_approve_continue_for_guard_review() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = PendingGateControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    action = await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={"approval_id": "grd-1", "status": "PENDING"},
        resolved_approval={
            "approval_id": "grd-1",
            "session_id": "sess-guard-1",
            "issue_id": "ISS-GUARD-1",
            "request_type": "guard_rejection_payload",
            "status": "APPROVED",
            "updated_at": "2026-03-24T12:00:00+00:00",
        },
    )

    assert action.input_class is OperatorInputClass.COMMAND
    assert action.command_class is OperatorCommandClass.APPROVE_CONTINUE
    assert action.target_ref == "approval-request:grd-1"


@pytest.mark.asyncio
async def test_pending_gate_operator_service_publishes_terminal_command_for_denial() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = PendingGateControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    action = await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={"approval_id": "grd-2", "status": "PENDING"},
        resolved_approval={
            "approval_id": "grd-2",
            "request_type": "guard_rejection_payload",
            "status": "DENIED",
            "updated_at": "2026-03-24T12:01:00+00:00",
        },
    )

    assert action.input_class is OperatorInputClass.COMMAND
    assert action.command_class is OperatorCommandClass.MARK_TERMINAL
