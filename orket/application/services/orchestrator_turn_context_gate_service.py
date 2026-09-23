from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_contract_input_capture import capture_mapping


class OrchestratorTurnContextGateService:
    def __init__(
        self,
        *,
        pending_gates: Any,
        create_pending_tool_approval_request: Callable[..., Awaitable[str]],
    ) -> None:
        self.pending_gates = pending_gates
        self.create_pending_tool_approval_request = create_pending_tool_approval_request

    async def find_existing_tool_approval_request(
        self,
        *,
        destination: TurnArtifactDestination,
        tool_name: str,
        tool_args: dict[str, Any],
        allowed_statuses: set[str],
    ) -> dict[str, Any] | None:
        list_requests = getattr(self.pending_gates, "list_requests", None)
        if not callable(list_requests):
            return None
        expected_target_ref = destination.control_plane_run_id
        tool_args = capture_mapping(tool_args)
        rows = await list_requests(session_id=destination.session_id, limit=1000)
        for row in rows:
            if str(row.get("status") or "").strip().lower() not in allowed_statuses:
                continue
            if str(row.get("issue_id") or "").strip() != destination.issue_id:
                continue
            if str(row.get("seat_name") or "").strip() != destination.role_name:
                continue
            if str(row.get("request_type") or "").strip() != "tool_approval":
                continue
            if str(row.get("reason") or "").strip() != f"approval_required_tool:{tool_name}":
                continue
            payload = row.get("payload_json")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("tool") or "").strip() != tool_name:
                continue
            if dict(payload.get("args") or {}) != dict(tool_args or {}):
                continue
            if payload.get("turn_index") != destination.turn_index:
                continue
            target_ref = str(payload.get("control_plane_target_ref") or "").strip()
            if target_ref != expected_target_ref:
                raise RuntimeError(
                    "approved governed turn-tool approval drifted from the admitted governed turn target"
                )
            return dict(row)
        return None

    def build_callbacks(
        self,
        *,
        gate_mode: str,
        issue_status: str,
    ) -> tuple[Callable[..., Awaitable[str]], Callable[..., Awaitable[str | None]]]:
        async def _pending_gate_request_writer(*, destination: TurnArtifactDestination, tool_name: str, tool_args: dict[str, Any]) -> str:
            tool_args = capture_mapping(tool_args)
            existing = await self.find_existing_tool_approval_request(
                destination=destination,
                tool_name=tool_name,
                tool_args=tool_args,
                allowed_statuses={"pending"},
            )
            if existing is not None:
                return str(existing.get("request_id") or "")
            return str(
                await self.create_pending_tool_approval_request(
                    destination=destination, issue_status=issue_status, gate_mode=gate_mode,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
            )

        async def _approved_tool_request_lookup(*, destination: TurnArtifactDestination, tool_name: str, tool_args: dict[str, Any]) -> str | None:
            existing = await self.find_existing_tool_approval_request(
                destination=destination,
                tool_name=tool_name,
                tool_args=tool_args,
                allowed_statuses={"approved"},
            )
            if existing is None:
                return None
            resolution = existing.get("resolution_json")
            if isinstance(resolution, dict) and str(resolution.get("decision") or "").strip().lower() != "approve":
                return None
            return str(existing.get("request_id") or "").strip() or None

        return _pending_gate_request_writer, _approved_tool_request_lookup
