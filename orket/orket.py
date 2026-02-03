# orket/orket.py
import json
import os
from typing import List

from venues.venue_loader import load_venue
from bands.band_loader import load_band
from scores.score_loader import load_score
from dispatcher import ToolDispatcher
from orket.filesystem import FilesystemPolicy
from orket.utils import log_event
from orket.agents.agent import Agent
from orket.session import Session
from orket.prelude import run_prelude


def build_filesystem_policy(permissions_path: str, policy_path: str) -> FilesystemPolicy:
    with open(permissions_path, "r", encoding="utf-8") as f:
        spaces = json.load(f)

    with open(policy_path, "r", encoding="utf-8") as f:
        policy = json.load(f)

    return FilesystemPolicy(spaces, policy)


def route_by_status(agent_name: str, content: str, structured_status: dict, completed_agents: set):
    if structured_status is None:
        return "continue"

    if structured_status.get("task_complete"):
        completed_agents.add(agent_name)
        return "agent_complete"

    status = structured_status.get("status")

    if status == "waiting" and structured_status.get("for", "").startswith("tool:"):
        tool_name = structured_status["for"].split("tool:", 1)[1]
        return ("wait_for_tool", tool_name, structured_status.get("args", {}))

    if status == "pending":
        return "pending"

    if status == "complete":
        completed_agents.add(agent_name)
        return "agent_complete"

    return "continue"


def execute_tool(dispatcher: ToolDispatcher, tool_name: str, args: dict) -> dict:
    return dispatcher.execute(tool_name, args)


def handle_tool_wait(dispatcher: ToolDispatcher, agent_name: str, tool_name: str, tool_args: dict, session: Session):
    result = execute_tool(dispatcher, tool_name, tool_args)

    log_event(
        "info",
        "tool",
        "tool_execution",
        {
            "agent": agent_name,
            "tool": tool_name,
            "args": tool_args,
            "result": result,
        },
    )

    session.add_message(
        role="tool",
        content=json.dumps(
            {
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            }
        ),
    )


def get_ready_roles(score, completed_agents: set, all_roles: List[str]) -> List[str]:
    # If included_roles is set, restrict to that subset; otherwise use all band roles
    candidate_roles = score.included_roles or all_roles

    ready: List[str] = []
    for role in candidate_roles:
        if role in completed_agents:
            continue

        required = score.dependencies.get(role, [])
        if all(r in completed_agents for r in required):
            ready.append(role)

    return ready


def orchestrate(venue_name: str, task: str, max_rounds: int = 20, use_prelude: bool = True) -> dict:
    venue = load_venue(venue_name)
    band = load_band(venue.band)
    score = load_score(venue.score)

    fs_policy = build_filesystem_policy(
        permissions_path=os.path.join(os.getcwd(), venue.permissions_file),
        policy_path=os.path.join(os.getcwd(), venue.policy_file),
    )
    dispatcher = ToolDispatcher(fs_policy)

    session = Session.start(venue_name=venue.name, task=task)
    completed_agents: set = set()

    if use_prelude and "architect" in band.roles:
        prelude_content = run_prelude(
            architect_prompt=band.roles["architect"].prompt,
            task=task,
        )
        session.add_message(role="architect", content=prelude_content)

    # Instantiate agents from band roles; score only constrains participation
    agents = {
        role_name: Agent(role=role_name, system_prompt=role_cfg.prompt)
        for role_name, role_cfg in band.roles.items()
    }

    all_role_names = list(band.roles.keys())

    for round_num in range(1, max_rounds + 1):
        ready_roles = get_ready_roles(score, completed_agents, all_role_names)

        if not ready_roles:
            break

        for role in ready_roles:
            agent = agents[role]

            content = agent.run(
                messages=[{"role": m.role, "content": m.content} for m in session.messages],
                round_num=round_num,
            )

            structured_status = None
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and (
                    "status" in parsed or "task_complete" in parsed
                ):
                    structured_status = parsed
            except Exception:
                pass

            decision = route_by_status(role, content, structured_status, completed_agents)

            session.add_message(role=role, content=content)

            if isinstance(decision, tuple) and decision[0] == "wait_for_tool":
                _, tool_name, tool_args = decision
                handle_tool_wait(dispatcher, role, tool_name, tool_args, session)

    return session.to_dict()
