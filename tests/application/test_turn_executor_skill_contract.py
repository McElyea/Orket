from __future__ import annotations

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
    async def execute(self, tool_name, args, context=None):
        return {"ok": True, "tool": tool_name, "args": args}


def _context() -> dict:
    return {
        "session_id": "sess-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
    }


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer")


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


@pytest.mark.asyncio
async def test_turn_executor_rejects_undeclared_skill_entrypoint_tool(tmp_path: Path) -> None:
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    context = _context()
    context["skill_contract_enforced"] = True
    context["skill_tool_bindings"] = {
        "read_file": {
            "entrypoint_id": "read-main",
            "tool_profile_id": "read_file",
            "tool_profile_version": "1.0.0",
            "required_permissions": {},
        }
    }

    result = await executor.execute_turn(_issue(), _role(), _Model(), _ToolBox(), context)
    assert result.success is False
    assert any("undeclared entrypoint/tool 'write_file'" in item for item in (result.violations or []))


@pytest.mark.asyncio
async def test_turn_executor_rejects_tool_when_required_permission_missing(tmp_path: Path) -> None:
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    context = _context()
    context["skill_contract_enforced"] = True
    context["skill_tool_bindings"] = {
        "write_file": {
            "entrypoint_id": "write-main",
            "tool_profile_id": "write_file",
            "tool_profile_version": "1.0.0",
            "required_permissions": {"filesystem": ["write"]},
        }
    }
    context["granted_permissions"] = {"filesystem": ["read"]}

    result = await executor.execute_turn(_issue(), _role(), _Model(), _ToolBox(), context)
    assert result.success is False
    assert any("missing required permissions" in item for item in (result.violations or []))

