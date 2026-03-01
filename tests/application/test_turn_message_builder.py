from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", name="Demo", seat="coder", status="in_progress")


def _role() -> RoleConfig:
    return RoleConfig(id="coder", name="coder", description="Writes code", prompt="You are coder", tools=["write_file"])


async def test_message_builder_includes_execution_context(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "required_action_tools": ["write_file"],
        "required_statuses": ["done"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "history": [{"role": "user", "content": "prior"}],
    }
    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)
    assert "Execution Context JSON" in rendered
    assert "Write Path Contract" in rendered
