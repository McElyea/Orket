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


@pytest.mark.asyncio
async def test_turn_executor_guard_rejection_payload_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Missing evidence", "violations": ["No tests"], "remediation_actions": ["Add tests"]}',
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
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 1
    assert toolbox.calls[0][1]["status"] == "blocked"


@pytest.mark.asyncio
async def test_turn_executor_guard_rejection_payload_contract_fails_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
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
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "guard rejection payload contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_guard_payload_reprompt_still_enforces_progress_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}',
            '{"tool": "add_issue_comment", "args": {"comment": "Need more detail"}}',
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
    context["stage_gate_mode"] = "review_required"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "progress contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_prepare_messages_includes_guard_rejection_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "stage_gate_mode": "review_required",
            "required_action_tools": ["update_issue_status"],
            "required_statuses": ["done", "blocked"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "Guard Rejection Contract" in joined
    assert "remediation_actions" in joined


@pytest.mark.asyncio
async def test_turn_executor_guard_dependency_block_rejected_when_dependencies_resolved(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Dependency unresolved", "violations": ["dep"], "remediation_actions": ["wait"]}',
            '{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "dependency"}}\n'
            '{"rationale": "Dependency unresolved", "violations": ["dep"], "remediation_actions": ["wait"]}',
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
    context["stage_gate_mode"] = "review_required"
    context["dependency_context"] = {
        "depends_on": ["ARC-1"],
        "dependency_count": 1,
        "dependency_statuses": {"ARC-1": "done"},
        "unresolved_dependencies": [],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "guard rejection payload contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_prepare_messages_includes_read_path_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "required_action_tools": ["read_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_read_paths": ["agent_output/main.py"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "Read Path Contract" in joined
    assert "agent_output/main.py" in joined


@pytest.mark.asyncio
async def test_prepare_messages_includes_write_path_contract(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    messages = await executor._prepare_messages(
        _issue(),
        _role(),
        {
            **_context(),
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_statuses": ["code_review"],
            "required_write_paths": ["agent_output/main.py"],
        },
        None,
    )
    joined = "\n".join(str(m.get("content", "")) for m in messages)
    assert "Write Path Contract" in joined
    assert "agent_output/main.py" in joined


@pytest.mark.asyncio
async def test_turn_executor_write_path_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/not_main.py", "content": "print(1)"}}'
            '\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/main.py", "content": "print(1)"}}'
            '\n{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="COD",
        summary="coder",
        description="Implement code",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "coder"
    context["roles"] = ["coder"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_write_paths"] = ["agent_output/main.py"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_read_path_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "/path/to/implementation/file"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["required_read_paths"] = ["agent_output/main.py"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_hallucination_scope_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": ["agent_output/main.py"],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2
    assert toolbox.calls[0][1]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_turn_executor_hallucination_scope_contract_fails_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "read_file", "args": {"path": "agent_output/not_allowed.py"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["read_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["read_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": ["agent_output/main.py"],
        "provided_context": [],
        "declared_interfaces": ["read_file", "update_issue_status"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_invented_detail_fails_under_strict_grounding(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nI assume this should work.',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nI assume this should work.',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "strict_grounding": True,
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_hallucination_contradiction_detects_forbidden_phrase(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nNo tests were run.',
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}\nNo tests were run.',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="REV",
        summary="code_reviewer",
        description="Review code",
        tools=["update_issue_status"],
    )
    context = _context()
    context["role"] = "code_reviewer"
    context["roles"] = ["code_reviewer"]
    context["required_action_tools"] = ["update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["verification_scope"] = {
        "workspace": [],
        "provided_context": [],
        "declared_interfaces": ["update_issue_status"],
        "forbidden_phrases": ["no tests were run"],
    }

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert len(toolbox.calls) == 0
    assert "hallucination scope contract not met after corrective reprompt" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_recovers_after_reprompt(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "plain text design"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"confidence\\": 0.82, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "architect_decides"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is True
    assert model.calls == 2
    assert len(toolbox.calls) == 2


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_enforces_forced_pattern(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 1, \\"independent_scaling_needs\\": \\"low\\", \\"deployment_complexity\\": \\"low\\", \\"team_parallelism\\": \\"single\\", \\"operational_maturity\\": \\"low\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"monolith\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 1, \\"external_integrations\\": 1, \\"independent_scaling_needs\\": \\"low\\", \\"deployment_complexity\\": \\"low\\", \\"team_parallelism\\": \\"single\\", \\"operational_maturity\\": \\"low\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "force_microservices"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["architecture_forced_pattern"] = "microservices"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert "architecture decision contract not met" in (result.error or "")


@pytest.mark.asyncio
async def test_turn_executor_architecture_contract_enforces_forced_frontend_framework(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    model = _Model(
        [
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"frontend_framework\\": \\"react\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
            '{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "{\\"recommendation\\": \\"microservices\\", \\"frontend_framework\\": \\"react\\", \\"confidence\\": 0.9, \\"evidence\\": {\\"estimated_domains\\": 4, \\"external_integrations\\": 3, \\"independent_scaling_needs\\": \\"high\\", \\"deployment_complexity\\": \\"high\\", \\"team_parallelism\\": \\"multi-team\\", \\"operational_maturity\\": \\"med\\"}}"}}\n'
            '{"tool": "update_issue_status", "args": {"status": "code_review"}}',
        ]
    )
    toolbox = _ToolBox()
    role = RoleConfig(
        id="ARC",
        summary="architect",
        description="Design architecture",
        tools=["write_file", "update_issue_status"],
    )
    context = _context()
    context["role"] = "architect"
    context["roles"] = ["architect"]
    context["required_action_tools"] = ["write_file", "update_issue_status"]
    context["required_statuses"] = ["code_review"]
    context["architecture_decision_required"] = True
    context["architecture_mode"] = "architect_decides"
    context["architecture_decision_path"] = "agent_output/design.txt"
    context["architecture_allowed_patterns"] = ["monolith", "microservices"]
    context["frontend_framework_allowed"] = ["vue", "react", "angular"]
    context["frontend_framework_forced"] = "angular"

    result = await executor.execute_turn(_issue(), role, model, toolbox, context)
    assert result.success is False
    assert model.calls == 2
    assert "architecture decision contract not met" in (result.error or "")
