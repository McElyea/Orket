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
