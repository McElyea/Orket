from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import IssueConfig, RoleConfig


class _Model:
    async def complete(self, _messages):
        return {
            "content": '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}',
            "raw": {"total_tokens": 1},
        }


class _ToolBox:
    def __init__(self):
        self.calls = 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        return {"ok": True, "tool": tool_name, "call_count": self.calls}


def _context(resume_mode: bool):
    return {
        "session_id": "run-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
        "resume_mode": resume_mode,
    }


def _issue():
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer")


def _role():
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


@pytest.mark.asyncio
async def test_turn_executor_checkpoint_and_resume_tool_replay(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model()
    toolbox = _ToolBox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=False))
    assert first.success is True
    assert toolbox.calls == 1

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    assert second.success is True
    assert toolbox.calls == 1

    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    checkpoint = json.loads((turn_dir / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["run_id"] == "run-1"
    assert checkpoint["issue_id"] == "ISSUE-1"
    assert checkpoint["turn_index"] == 1
    assert checkpoint["model"] == "dummy"
    assert checkpoint["tool_calls"][0]["tool"] == "write_file"
