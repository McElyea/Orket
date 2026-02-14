from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.middleware import MiddlewareOutcome, MiddlewarePipeline
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import IssueConfig, RoleConfig


class _ToolBox:
    def __init__(self):
        self.calls = []

    async def execute(self, tool_name, args, context=None):
        self.calls.append((tool_name, args))
        return {"ok": True, "tool": tool_name}


class _Model:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def complete(self, _messages):
        self.calls += 1
        idx = min(self.calls - 1, len(self.outputs) - 1)
        return {"content": self.outputs[idx], "raw": {"total_tokens": 1}}


def _context():
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


def _issue():
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer")


def _role():
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


@pytest.mark.asyncio
async def test_turn_executor_middleware_hook_order(tmp_path):
    hook_order = []

    class _Hooks:
        def before_prompt(self, messages, **_kwargs):
            hook_order.append("before_prompt")
            return MiddlewareOutcome(replacement=messages)

        def after_model(self, response, **_kwargs):
            hook_order.append("after_model")
            return MiddlewareOutcome(replacement=response)

        def before_tool(self, tool_name, args, **_kwargs):
            hook_order.append(f"before_tool:{tool_name}")
            return None

        def after_tool(self, tool_name, args, result, **_kwargs):
            hook_order.append(f"after_tool:{tool_name}")
            return MiddlewareOutcome(replacement=result)

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=MiddlewarePipeline([_Hooks()]),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is True
    assert hook_order == ["before_prompt", "after_model", "before_tool:write_file", "after_tool:write_file"]


@pytest.mark.asyncio
async def test_turn_executor_middleware_short_circuit_before_tool(tmp_path):
    class _Hooks:
        def before_tool(self, tool_name, args, **_kwargs):
            return MiddlewareOutcome(short_circuit=True, reason="blocked by middleware")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=MiddlewarePipeline([_Hooks()]),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is False
    assert "blocked by middleware" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_calls_on_turn_failure_hook(tmp_path):
    hit = {"called": False}

    class _Hooks:
        def on_turn_failure(self, error, **_kwargs):
            hit["called"] = True

    class _FailingModel:
        async def complete(self, _messages):
            raise RuntimeError("boom")

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        middleware=MiddlewarePipeline([_Hooks()]),
    )
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), _FailingModel(), toolbox, _context())
    assert result.success is False
    assert hit["called"] is True


@pytest.mark.asyncio
async def test_turn_executor_non_progress_fails_after_one_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(["No-op", "Still no-op"])
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is False
    assert model.calls == 2
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_non_progress_recovery_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            "No-op",
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}',
        ]
    )
    toolbox = _ToolBox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 1


@pytest.mark.asyncio
async def test_turn_executor_context_only_tool_call_is_non_progress(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "get_issue_context", "args": {}}',
            '{"tool": "get_issue_context", "args": {}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REQ",
        summary="requirements_analyst",
        description="Gather requirements",
        tools=["get_issue_context", "write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "requirements_analyst"
    context["roles"] = ["requirements_analyst"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_enforces_required_status_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}\n{"tool": "update_issue_status", "args": {"status": "in_progress"}}',
            '{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REQ",
        summary="requirements_analyst",
        description="Gather requirements",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "requirements_analyst"
    context["roles"] = ["requirements_analyst"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[1][1]["status"] == "code_review"


@pytest.mark.asyncio
async def test_turn_executor_blocked_requires_wait_reason(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="GRD",
        summary="integrity_guard",
        description="Final gate",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "integrity_guard"
    context["roles"] = ["integrity_guard"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["done", "blocked"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "Deterministic failure" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_blocks_approval_required_tool_and_persists_request(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(['{"tool": "write_file", "args": {"path": "out.txt", "content": "ok"}}'])
    toolbox = _ToolBox()

    request_calls = []

    async def _request_writer(*, tool_name, tool_args):
        request_calls.append({"tool_name": tool_name, "tool_args": tool_args})
        return "REQ-TOOL-1"

    context = _context()
    context["approval_required_tools"] = ["write_file"]
    context["create_pending_gate_request"] = _request_writer
    context["stage_gate_mode"] = "approval_required"

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, context)

    assert result.success is False
    assert result.should_retry is True
    assert "Approval required for tool 'write_file'" in (result.error or "")
    assert len(toolbox.calls) == 0
    assert len(request_calls) == 1
    assert request_calls[0]["tool_name"] == "write_file"
