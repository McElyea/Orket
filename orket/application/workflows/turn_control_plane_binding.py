"""Retain the existing dispatcher and control-plane owner for one invocation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService
from orket.application.services.turn_tool_control_plane_support import run_namespace_scope

if TYPE_CHECKING:
    from .turn_tool_dispatcher import ToolDispatcher


@dataclass(frozen=True, slots=True)
class TurnControlPlaneBinding:
    dispatcher: ToolDispatcher
    service: TurnToolControlPlaneService | None
    namespace_scope: str
    resume_mode: bool
    protocol_replay_mode: bool


def capture_turn_control_plane_binding(
    *, dispatcher: ToolDispatcher, issue_id: str, context: dict[str, Any],
) -> TurnControlPlaneBinding:
    return TurnControlPlaneBinding(
        dispatcher=dispatcher,
        service=dispatcher.control_plane_service,
        namespace_scope=run_namespace_scope(issue_id=issue_id, context=context),
        resume_mode=bool(context.get("resume_mode")),
        protocol_replay_mode=bool(context.get("protocol_replay_mode")),
    )
