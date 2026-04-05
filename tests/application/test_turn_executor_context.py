import json
from pathlib import Path

import pytest
from types import SimpleNamespace

from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import CardStatus, IssueConfig, RoleConfig


def _write_prompt_budget_policy(path: Path, *, max_tokens: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
schema_version: "1.0"
budget_policy_version: "1.0"
stages:
  planner:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
  executor:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
  reviewer:
    max_tokens: {max_tokens}
    protocol_tokens: {max_tokens}
    tool_schema_tokens: {max_tokens}
    task_tokens: {max_tokens}
""".strip()
        + "\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_prepare_messages_includes_dependency_context_block(tmp_path):
    """Layer: contract. Verifies compact turn packets preserve dependency context instead of verbose JSON blocks."""
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
    assert [message["role"] for message in messages] == ["system", "user"]
    rendered = messages[1]["content"]
    assert "TURN PACKET:" in rendered
    assert "Dependency Context:" in rendered
    assert "- dependency_count: 2" in rendered
    assert "- depends_on: REQ-1, ARC-1" in rendered


@pytest.mark.asyncio
async def test_execute_turn_writes_prompt_provenance_artifacts(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(
        id="DEV",
        summary="developer",
        description="Builds code",
        tools=["write_file"],
    )

    class _ModelClient:
        async def complete(self, messages):
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-1",
        "turn_index": 0,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "dependency_context": {},
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "stage_gate_mode": "auto",
        "history": [],
        "prompt_metadata": {
            "prompt_id": "role.developer+dialect.generic",
            "prompt_version": "1.0.0/1.0.0",
            "prompt_checksum": "abc123",
            "resolver_policy": "resolver_v1",
        },
        "prompt_layers": {
            "role_base": {"name": "developer", "version": "1.0.0"},
            "dialect_adapter": {"name": "generic", "version": "1.0.0", "prefix_applied": False},
            "guards": [],
            "context_profile": "default",
        },
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )

    assert result.success is True
    out_dir = Path(tmp_path) / "observability" / "sess-1" / "ISSUE-1" / "000_developer"
    layers = json.loads((out_dir / "prompt_layers.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((out_dir / "checkpoint.json").read_text(encoding="utf-8"))

    assert layers["role_base"]["name"] == "developer"
    assert checkpoint["prompt_metadata"]["prompt_id"] == "role.developer+dialect.generic"
    assert checkpoint["prompt_metadata"]["resolver_policy"] == "resolver_v1"


@pytest.mark.asyncio
async def test_execute_turn_reprompt_overwrites_response_artifacts_with_accepted_response(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(
        id="DEV",
        summary="developer",
        description="Builds code",
        tools=["write_file", "update_issue_status"],
    )

    class _ModelClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages):
            _ = messages
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content='{"tool":"write_file","args":{"path":"agent_output/other.py","content":"print(1)"}}',
                    raw={"response_id": "first"},
                )
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}'
                '\n{"tool":"update_issue_status","args":{"status":"code_review"}}',
                raw={"response_id": "second"},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True, "tool": tool_name, "args": args}

    context = {
        "session_id": "sess-reprompt",
        "turn_index": 1,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "dependency_context": {},
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "stage_gate_mode": "auto",
        "history": [],
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )

    assert result.success is True
    out_dir = Path(tmp_path) / "observability" / "sess-reprompt" / "ISSUE-1" / "001_developer"
    assert "agent_output/main.py" in (out_dir / "model_response.txt").read_text(encoding="utf-8")
    response_raw = json.loads((out_dir / "model_response_raw.json").read_text(encoding="utf-8"))
    parsed_calls = json.loads((out_dir / "parsed_tool_calls.json").read_text(encoding="utf-8"))
    assert response_raw["response_id"] == "second"
    assert parsed_calls[0]["args"]["path"] == "agent_output/main.py"


@pytest.mark.asyncio
async def test_execute_turn_writes_prompt_budget_and_structure_artifacts(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["write_file"])
    policy_path = Path(tmp_path) / "core" / "policies" / "prompt_budget.yaml"
    _write_prompt_budget_policy(policy_path, max_tokens=5000)

    class _ModelClient:
        async def count_tokens(self, messages):
            total_chars = sum(len(str((row or {}).get("content") or "")) for row in messages if isinstance(row, dict))
            return {"token_count": max(1, total_chars // 4), "tokenizer_id": "test-tokenizer"}

        async def complete(self, messages):
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-2",
        "turn_index": 1,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "dependency_context": {},
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "stage_gate_mode": "auto",
        "history": [],
        "prompt_budget_enabled": True,
        "prompt_budget_require_backend_tokenizer": True,
        "prompt_budget_policy_path": str(policy_path),
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )

    assert result.success is True
    out_dir = Path(tmp_path) / "observability" / "sess-2" / "ISSUE-1" / "001_developer"
    budget = json.loads((out_dir / "prompt_budget_usage.json").read_text(encoding="utf-8"))
    structure = json.loads((out_dir / "prompt_structure.json").read_text(encoding="utf-8"))
    assert budget["ok"] is True
    assert budget["tokenizer_source"] == "backend"
    assert structure["tokenizer_id"] == "test-tokenizer"


@pytest.mark.asyncio
async def test_execute_turn_fails_closed_when_prompt_budget_exceeded(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["write_file"])
    policy_path = Path(tmp_path) / "core" / "policies" / "prompt_budget.yaml"
    _write_prompt_budget_policy(policy_path, max_tokens=10)
    call_count = {"value": 0}

    class _ModelClient:
        async def complete(self, messages):
            call_count["value"] += 1
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True}

    context = {
        "session_id": "sess-3",
        "turn_index": 1,
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "dependency_context": {},
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "stage_gate_mode": "auto",
        "history": [],
        "prompt_budget_enabled": True,
        "prompt_budget_require_backend_tokenizer": False,
        "prompt_budget_policy_path": str(policy_path),
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=_ModelClient(),
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )

    assert result.success is False
    assert "E_PROMPT_BUDGET_EXCEEDED" in str(result.error or "")
    assert call_count["value"] == 0


@pytest.mark.asyncio
async def test_execute_turn_rejects_ready_turn_context(tmp_path):
    """Layer: contract. Verifies execute_turn requires an active turn status instead of READY."""

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.READY)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["write_file"])

    class _ModelClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages):
            self.calls += 1
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True}

    model = _ModelClient()
    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=model,
        toolbox=_Toolbox(),
        context={
            "session_id": "sess-ready",
            "turn_index": 0,
            "issue_id": "ISSUE-1",
            "role": "developer",
            "roles": ["developer"],
            "current_status": "ready",
            "selected_model": "dummy-model",
            "history": [],
        },
        system_prompt="SYSTEM",
    )

    assert result.success is False
    assert "cannot execute turn from context status ready" in str(result.error or "")
    assert model.calls == 0


@pytest.mark.asyncio
async def test_execute_turn_rejects_status_context_mismatch(tmp_path):
    """Layer: contract. Verifies execute_turn fails fast when issue.status and context.current_status diverge."""

    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(id="DEV", summary="developer", description="Builds code", tools=["write_file"])

    class _ModelClient:
        def __init__(self) -> None:
            self.calls = 0

        async def complete(self, messages):
            self.calls += 1
            return SimpleNamespace(
                content='{"tool":"write_file","args":{"path":"agent_output/main.py","content":"print(1)"}}',
                raw={"total_tokens": 7},
            )

    class _Toolbox:
        async def execute(self, tool_name, args, context=None):
            return {"ok": True}

    model = _ModelClient()
    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=model,
        toolbox=_Toolbox(),
        context={
            "session_id": "sess-mismatch",
            "turn_index": 0,
            "issue_id": "ISSUE-1",
            "role": "developer",
            "roles": ["developer"],
            "current_status": "code_review",
            "selected_model": "dummy-model",
            "history": [],
        },
        system_prompt="SYSTEM",
    )

    assert result.success is False
    assert "status/context mismatch" in str(result.error or "")
    assert model.calls == 0

