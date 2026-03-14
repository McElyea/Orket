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


async def test_message_builder_serializes_history_as_user_block(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [
            {"role": "coder", "content": "write main.py"},
            {"role": "integrity_guard", "content": "blocked: missing tests"},
        ],
    }
    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    history_messages = [m for m in messages if m.get("content", "").startswith("Prior Transcript JSON:\n")]
    assert len(history_messages) == 1
    assert history_messages[0]["role"] == "user"
    assert '"actor": "coder"' in history_messages[0]["content"]
    assert '"actor": "integrity_guard"' in history_messages[0]["content"]


async def test_message_builder_adds_protocol_response_contract_when_governed(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "protocol_governed_enabled": True,
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    protocol_messages = [m for m in messages if m.get("content", "").startswith("Protocol Response Contract:\n")]

    assert len(protocol_messages) == 1
    assert '"content":"","tool_calls"' in protocol_messages[0]["content"]
    assert "Do not use markdown fences" in protocol_messages[0]["content"]
