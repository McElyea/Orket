from __future__ import annotations

from orket.application.services.turn_tool_control_plane_support import run_id_for


def test_turn_tool_run_id_format_is_stable() -> None:
    """Layer: unit. Verifies turn-tool control-plane run ids retain prefix, separators, and zero-padded turn index."""
    assert (
        run_id_for(
            session_id="sess-1",
            issue_id="ISSUE-1",
            role_name="Lead Architect",
            turn_index=7,
        )
        == "turn-tool-run:sess-1:ISSUE-1:lead_architect:0007"
    )
