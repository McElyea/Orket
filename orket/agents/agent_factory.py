# orket/agents/agent_factory.py

from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.agents.agent import Agent
from orket.logging import log_event
from orket.tools import ToolBox, get_tool_map


def build_team_agents(team: Any, provider: LocalModelProvider, toolbox: ToolBox) -> dict[str, Agent]:
    """
    Factory to instantiate agents for a specific Team.
    """
    agents: dict[str, Agent] = {}
    tool_map = get_tool_map(toolbox)
    role_configs = _role_configs_by_name(team)

    for seat_name, seat in team.seats.items():
        allowed_tools = _allowed_tools_for_seat(
            team_name=str(getattr(team, "name", "") or ""),
            seat_name=str(seat_name),
            seat=seat,
            role_configs=role_configs,
        )
        scoped_tool_map = {name: tool for name, tool in tool_map.items() if name in allowed_tools}

        agents[seat_name] = Agent(
            name=seat_name,
            description=f"Member of team {team.name} in seat {seat_name}",
            tools=scoped_tool_map,
            provider=provider,
            strict_config=bool(scoped_tool_map),
        )

    return agents


def _role_configs_by_name(team: Any) -> dict[str, Any]:
    raw_roles = getattr(team, "roles", None)
    if not isinstance(raw_roles, dict):
        return {}
    return {str(role_name).strip(): role for role_name, role in raw_roles.items() if str(role_name).strip()}


def _allowed_tools_for_seat(
    *,
    team_name: str,
    seat_name: str,
    seat: Any,
    role_configs: dict[str, Any],
) -> set[str]:
    role_names = [str(role).strip() for role in list(getattr(seat, "roles", []) or []) if str(role).strip()]
    if not role_names:
        log_event(
            "seat_no_roles_configured",
            {"team": team_name, "seat": seat_name},
            level="warn",
        )
        return set()
    allowed_tools: set[str] = set()
    for role_name in role_names:
        role_config = role_configs.get(role_name)
        if role_config is None:
            log_event(
                "seat_role_config_missing",
                {"team": team_name, "seat": seat_name, "role": role_name},
                level="warn",
            )
            continue
        allowed_tools.update(_tool_names_for_role(role_config))
    return allowed_tools


def _tool_names_for_role(role_config: Any) -> set[str]:
    raw_tools = role_config.get("tools", []) if isinstance(role_config, dict) else getattr(role_config, "tools", [])
    return {str(tool).strip() for tool in list(raw_tools or []) if str(tool).strip()}
