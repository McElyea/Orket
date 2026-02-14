import json
from pathlib import Path

import pytest
from types import SimpleNamespace

from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import CardStatus, IssueConfig, RoleConfig


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


@pytest.mark.asyncio
async def test_execute_turn_writes_prompt_provenance_artifacts(tmp_path):
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
    )
    issue = IssueConfig(id="ISSUE-1", summary="Implement feature", status=CardStatus.READY)
    role = RoleConfig(
        id="DEV",
        summary="developer",
        description="Builds code",
        tools=["read_file", "update_issue_status"],
    )

    class _ModelClient:
        async def complete(self, messages):
            return SimpleNamespace(
                content='{"tool":"update_issue_status","args":{"issue_id":"ISSUE-1","status":"done"}}',
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
        "current_status": "ready",
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

