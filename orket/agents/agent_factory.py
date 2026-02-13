# orket/agents/agent_factory.py
from typing import Dict
from orket.agents.agent import Agent
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.tools import get_tool_map, ToolBox


def build_team_agents(team, provider: LocalModelProvider, toolbox: ToolBox) -> Dict[str, Agent]:
    """
    Factory to instantiate agents for a specific Team.
    """
    agents: Dict[str, Agent] = {}
    tool_map = get_tool_map(toolbox)

    for seat_name, seat in team.seats.items():
        # Aggregate tools for all roles in this seat
        resolved_tools = {}
        
        # Load the role objects if needed, or use the seat's role definitions
        # This is a bit complex as we usually load role JSONs in the traction loop.
        # This factory is mostly used for high-level setup or specialized tests.
        
        for role_name in seat.roles:
            # Placeholder: In the real traction loop, we load RoleConfigs.
            # Here we just register what tools are in the tool_map.
            pass

        agents[seat_name] = Agent(
            name=seat_name,
            description=f"Member of team {team.name} in seat {seat_name}",
            tools=tool_map, # Default to all tools for factory-built agents
            provider=provider,
        )

    return agents
