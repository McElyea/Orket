import json
from pathlib import Path

import pytest

from orket.orchestration.turn_executor import TurnExecutor
from orket.domain.state_machine import StateMachine
from orket.services.tool_gate import ToolGate
from orket.schema import IssueConfig, RoleConfig


@pytest.mark.asyncio
async def test_prepare_messages_includes_dependency_context_block(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", depends_on=["REQ-1", "ARC-1"])
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["write_file"])
    context = {
        "session_id": "sess-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "dependency_context": {"depends_on": ["REQ-1", "ARC-1"], "dependency_count": 2},
        "history": [],
    }

    messages = await executor._prepare_messages(issue, role, context)
    payloads = [m["content"] for m in messages if m["role"] == "user"]
    context_payload = next((p for p in payloads if p.startswith("Execution Context JSON:\n")), None)

    assert context_payload is not None
    parsed = json.loads(context_payload.split("\n", 1)[1])
    assert parsed["issue_id"] == "ISSUE-1"
    assert parsed["seat"] == "developer"
    assert parsed["dependency_context"]["depends_on"] == ["REQ-1", "ARC-1"]
    assert parsed["dependency_context"]["dependency_count"] == 2
