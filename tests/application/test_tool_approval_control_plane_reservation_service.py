# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.domain import ReservationKind, ReservationStatus
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_tool_approval_reservation_service_publishes_pending_operator_hold() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneReservationService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    reservation = await service.publish_pending_tool_approval_hold(
        approval_id="apr-1",
        session_id="sess-1",
        issue_id="ISS-1",
        seat_name="coder",
        tool_name="write_file",
        turn_index=1,
        created_at="2026-03-24T05:00:00+00:00",
        control_plane_target_ref="turn-tool-run:sess-1:ISS-1:coder:0001",
    )

    stored = await repository.get_latest_reservation_record(reservation_id=reservation.reservation_id)

    assert stored is not None
    assert stored.reservation_kind is ReservationKind.OPERATOR_HOLD
    assert stored.status is ReservationStatus.ACTIVE
    assert stored.holder_ref == "turn-tool-run:sess-1:ISS-1:coder:0001"
    assert "approval=approval-request:apr-1" in stored.target_scope_ref


@pytest.mark.asyncio
async def test_tool_approval_reservation_service_releases_hold_on_approval() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneReservationService(
        publication=ControlPlanePublicationService(repository=repository)
    )
    await service.publish_pending_tool_approval_hold(
        approval_id="apr-2",
        session_id="sess-2",
        issue_id="ISS-2",
        seat_name="coder",
        tool_name="write_file",
        turn_index=1,
        created_at="2026-03-24T05:01:00+00:00",
        control_plane_target_ref="turn-tool-run:sess-2:ISS-2:coder:0001",
    )

    released = await service.publish_resolved_tool_approval_hold(
        resolved_approval={
            "approval_id": "apr-2",
            "request_type": "tool_approval",
            "status": "APPROVED",
        }
    )

    assert released is not None
    assert released.status is ReservationStatus.RELEASED
    assert released.expiry_or_invalidation_basis == "approval_resolved_continue:approved"


@pytest.mark.asyncio
async def test_tool_approval_reservation_service_invalidates_terminal_hold_and_rejects_non_packet1_status() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneReservationService(
        publication=ControlPlanePublicationService(repository=repository)
    )
    await service.publish_pending_tool_approval_hold(
        approval_id="apr-3",
        session_id="sess-3",
        issue_id="ISS-3",
        seat_name="coder",
        tool_name="write_file",
        turn_index=1,
        created_at="2026-03-24T05:02:00+00:00",
        control_plane_target_ref="turn-tool-run:sess-3:ISS-3:coder:0001",
    )
    invalidated = await service.publish_resolved_tool_approval_hold(
        resolved_approval={
            "approval_id": "apr-3",
            "request_type": "tool_approval",
            "status": "DENIED",
        }
    )

    await service.publish_pending_tool_approval_hold(
        approval_id="apr-4",
        session_id="sess-4",
        issue_id="ISS-4",
        seat_name="coder",
        tool_name="write_file",
        turn_index=1,
        created_at="2026-03-24T05:03:00+00:00",
        control_plane_target_ref="turn-tool-run:sess-4:ISS-4:coder:0001",
    )
    with pytest.raises(ValueError, match="approved or denied"):
        await service.publish_resolved_tool_approval_hold(
            resolved_approval={
                "approval_id": "apr-4",
                "request_type": "tool_approval",
                "status": "EXPIRED",
            }
        )
    still_pending = await repository.get_latest_reservation_record(reservation_id="approval-reservation:apr-4")

    assert invalidated is not None
    assert invalidated.status is ReservationStatus.INVALIDATED
    assert still_pending is not None
    assert still_pending.status is ReservationStatus.ACTIVE


@pytest.mark.asyncio
async def test_tool_approval_reservation_service_supports_guard_review_hold_resolution() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = ToolApprovalControlPlaneReservationService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    pending = await service.publish_pending_guard_review_hold(
        request_id="grd-1",
        session_id="sess-guard-1",
        issue_id="ISS-GUARD-1",
        seat_name="integrity_guard",
        reason="missing_rationale",
        gate_mode="review_required",
        created_at="2026-03-24T05:04:00+00:00",
    )
    released = await service.publish_resolved_pending_gate_hold(
        resolved_approval={
            "approval_id": "grd-1",
            "request_type": "guard_rejection_payload",
            "reason": "missing_rationale",
            "status": "APPROVED",
        }
    )

    assert pending.status is ReservationStatus.ACTIVE
    assert released is not None
    assert released.status is ReservationStatus.RELEASED
    assert released.expiry_or_invalidation_basis == "pending_gate_resolved_continue:guard_rejection_payload:approved"
