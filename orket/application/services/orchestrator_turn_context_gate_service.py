from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from orket.schema import IssueConfig


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
        run_id: str,
        issue: IssueConfig,
        seat_name: str,
        turn_index: int,
        tool_name: str,
        tool_args: dict[str, Any],
        allowed_statuses: set[str],
    ) -> dict[str, Any] | None:
        list_requests = getattr(self.pending_gates, "list_requests", None)
        if not callable(list_requests):
            return None
        from orket.application.services.turn_tool_control_plane_support import run_id_for as turn_tool_run_id_for

        expected_target_ref = turn_tool_run_id_for(
            session_id=run_id,
            issue_id=issue.id,
            role_name=seat_name,
            turn_index=int(turn_index),
        )
        rows = await list_requests(session_id=run_id, limit=1000)
        for row in rows:
            if str(row.get("status") or "").strip().lower() not in allowed_statuses:
                continue
            if str(row.get("issue_id") or "").strip() != issue.id:
                continue
            if str(row.get("seat_name") or "").strip() != seat_name:
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
            if payload.get("turn_index") != int(turn_index):
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
        run_id: str,
        issue: IssueConfig,
        seat_name: str,
        gate_mode: str,
        turn_index: int,
    ) -> tuple[Callable[..., Awaitable[str]], Callable[..., Awaitable[str | None]]]:
        async def _pending_gate_request_writer(*, tool_name: str, tool_args: dict[str, Any]) -> str:
            existing = await self.find_existing_tool_approval_request(
                run_id=run_id,
                issue=issue,
                seat_name=seat_name,
                turn_index=turn_index,
                tool_name=tool_name,
                tool_args=tool_args,
                allowed_statuses={"pending"},
            )
            if existing is not None:
                return str(existing.get("request_id") or "")
            return str(
                await self.create_pending_tool_approval_request(
                    run_id=run_id,
                    issue=issue,
                    seat_name=seat_name,
                    gate_mode=gate_mode,
                    turn_index=turn_index,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
            )

        async def _approved_tool_request_lookup(*, tool_name: str, tool_args: dict[str, Any]) -> str | None:
            existing = await self.find_existing_tool_approval_request(
                run_id=run_id,
                issue=issue,
                seat_name=seat_name,
                turn_index=turn_index,
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
