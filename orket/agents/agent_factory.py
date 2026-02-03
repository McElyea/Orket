from orket.agents.agent import Agent


class AgentFactory:
    """
    Factory for constructing Agent instances from merged role configs.
    """

    @staticmethod
    def create(role_name: str, role_config: dict) -> Agent:
        """
        role_config is expected to be:
          { "standard": "<final merged prompt>" }
        """
        if "standard" not in role_config:
            raise ValueError(f"Role '{role_name}' missing 'standard' prompt variant")

        system_prompt = role_config["standard"]

        return Agent(role=role_name, system_prompt=system_prompt)

    @staticmethod
    def create_team(team_roles: list, merged_prompts: dict) -> dict:
        """
        Given a list of role names and the merged prompts from team_loader,
        return a dict of { role_name: Agent instance }.
        """
        agents = {}

        for role in team_roles:
            if role not in merged_prompts:
                raise ValueError(f"Role '{role}' missing from merged prompts")

            agents[role] = AgentFactory.create(role, merged_prompts[role])

        return agents
