"""Publish an approval request and its hold for one captured turn destination."""
from __future__ import annotations

from typing import Any

from .turn_artifact_destination import TurnArtifactDestination
from .turn_contract_input_capture import capture_mapping


async def create_pending_tool_approval_request(
    owner: Any, *, destination: TurnArtifactDestination, issue_status: str,
    gate_mode: str, tool_name: str, tool_args: dict[str, Any],
) -> str:
    create_request = owner.pending_gates.create_request
    publisher = getattr(owner, "tool_approval_control_plane_reservation", None)
    request_created_at = owner.turn_clock().isoformat()
    target_ref = destination.control_plane_run_id
    payload = capture_mapping({
        "tool": tool_name, "args": tool_args, "role": destination.role_name,
        "turn_index": destination.turn_index, "control_plane_target_ref": target_ref,
        "issue_status": issue_status,
    })
    request_id = str(await create_request(
        session_id=destination.session_id, issue_id=destination.issue_id,
        seat_name=destination.role_name, gate_mode=gate_mode, request_type="tool_approval",
        reason=f"approval_required_tool:{tool_name}", created_at=request_created_at, payload=payload,
    ))
    if publisher is not None:
        await publisher.publish_pending_tool_approval_hold(
            approval_id=request_id, session_id=destination.session_id, issue_id=destination.issue_id,
            seat_name=destination.role_name, tool_name=tool_name, turn_index=destination.turn_index,
            created_at=request_created_at, control_plane_target_ref=target_ref,
        )
    return request_id
