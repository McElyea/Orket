from __future__ import annotations

from typing import Any

from orket.application.services.kernel_action_control_plane_support import (
    run_id_for as kernel_action_run_id_for,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)


async def publish_pending_kernel_approval_hold_if_needed(
    *,
    engine: Any,
    session_id: str,
    trace_id: str,
    proposal: dict[str, Any],
    response: dict[str, Any],
) -> None:
    admission_decision = response.get("admission_decision")
    if not isinstance(admission_decision, dict):
        return
    if str(admission_decision.get("decision") or "").strip() != "NEEDS_APPROVAL":
        return
    approval_id = str(response.get("approval_id") or "").strip()
    if not approval_id:
        return
    publication = getattr(engine, "control_plane_publication", None)
    if publication is None:
        return
    approval = await engine.get_approval(approval_id)
    if not isinstance(approval, dict):
        return
    payload = proposal.get("payload")
    proposal_payload = payload if isinstance(payload, dict) else {}
    tool_name = str(proposal_payload.get("tool_name") or proposal.get("proposal_type") or "governed_action").strip()
    publisher = getattr(engine, "tool_approval_control_plane_reservation", None)
    if publisher is None or getattr(publisher, "publication", None) is not publication:
        publisher = ToolApprovalControlPlaneReservationService(publication=publication)
        engine.tool_approval_control_plane_reservation = publisher
    await publisher.publish_pending_tool_approval_hold(
        approval_id=approval_id,
        session_id=session_id,
        issue_id="",
        seat_name="kernel_action",
        tool_name=tool_name,
        turn_index=None,
        created_at=str(approval.get("created_at") or ""),
        control_plane_target_ref=kernel_action_run_id_for(session_id=session_id, trace_id=trace_id),
    )


__all__ = ["publish_pending_kernel_approval_hold_if_needed"]
