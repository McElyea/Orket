# Layer: unit

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from orket.agents.agent_factory import build_team_agents
from orket.application.services.toolbox import ToolBox
from orket.exceptions import AgentConfigurationError


class _Provider:
    model = "llama3"

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> str:
        return ""


def _toolbox_with_tools(tmp_path) -> ToolBox:
    toolbox = ToolBox({}, str(tmp_path), [], db_path=str(tmp_path / "cards.db"))
    toolbox.tool_strategy_node = SimpleNamespace(select_tools=lambda inputs: ("read_file", "write_file"))
    return toolbox


def test_build_team_agents_limits_tools_to_role_allowlist(tmp_path) -> None:
    team = SimpleNamespace(
        name="demo",
        seats={"coder": SimpleNamespace(roles=["coder"])},
        roles={"coder": SimpleNamespace(tools=["read_file"])},
    )

    agents = build_team_agents(team, _Provider(), _toolbox_with_tools(tmp_path))

    assert set(agents["coder"].tools) == {"read_file"}


def test_build_team_agents_assigns_no_tools_when_seat_has_no_roles(tmp_path) -> None:
    team = SimpleNamespace(
        name="demo",
        seats={"unassigned": SimpleNamespace(roles=[])},
        roles={"coder": SimpleNamespace(tools=["read_file"])},
    )

    with pytest.raises(AgentConfigurationError, match="seat has no executable tools"):
        build_team_agents(team, _Provider(), _toolbox_with_tools(tmp_path))


def test_build_team_agents_logs_error_when_role_config_is_missing(caplog, tmp_path) -> None:
    """Layer: unit. Verifies misconfigured role scopes are visible and fail closed."""
    team = SimpleNamespace(
        name="demo",
        seats={"coder": SimpleNamespace(roles=["missing_role"])},
        roles={},
    )
    caplog.set_level("ERROR", logger="orket")

    with pytest.raises(AgentConfigurationError, match="seat has no executable tools"):
        build_team_agents(team, _Provider(), _toolbox_with_tools(tmp_path))

    assert any(record.message == "seat_role_config_missing" for record in caplog.records)
    assert any(
        record.message == "seat_tool_scope_empty" and "missing_role" in str(getattr(record, "orket_record", {}))
        for record in caplog.records
    )
