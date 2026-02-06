# orket/agents/agent_factory.py
from typing import Dict
from orket.agents.agent import Agent
from orket.llm import LocalModelProvider
from orket.tools import TOOLS


def build_band_agents(band, provider: LocalModelProvider) -> Dict[str, Agent]:
    agents: Dict[str, Agent] = {}

    for role_name, role in band.roles.items():
        resolved_tools = {}

        for tool_name in role.tools:
            if tool_name not in TOOLS:
                raise RuntimeError(
                    f"Role '{role_name}' requires tool '{tool_name}', "
                    f"but it is not present in the tool registry."
                )
            resolved_tools[tool_name] = TOOLS[tool_name]

        agents[role_name] = Agent(
            name=role_name,
            description=role.description,
            tools=resolved_tools,
            provider=provider,
        )

    return agents
