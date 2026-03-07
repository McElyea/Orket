from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn, ToolCall


def _dispatcher(tmp_path: Path) -> ToolDispatcher:
    def _load_replay_tool_result(**_kwargs) -> dict[str, Any] | None:
        return None

    def _persist_tool_result(**_kwargs) -> None:
        return None

    def _load_operation_result(**_kwargs) -> dict[str, Any] | None:
        return None

    def _persist_operation_result(**_kwargs) -> None:
        return None

    def _append_protocol_receipt(**kwargs) -> dict[str, Any]:
        return dict(kwargs.get("receipt") or {})

    return ToolDispatcher(
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        middleware=TurnLifecycleInterceptors([]),
        workspace=tmp_path,
        append_memory_event=lambda *args, **kwargs: None,
        hash_payload=lambda payload: "hash",
        load_replay_tool_result=_load_replay_tool_result,
        persist_tool_result=_persist_tool_result,
        load_operation_result=_load_operation_result,
        persist_operation_result=_persist_operation_result,
        append_protocol_receipt=_append_protocol_receipt,
        tool_validation_error_factory=lambda violations: RuntimeError(str(violations)),
    )


class _NoOpToolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name, args, context):
        self.calls += 1
        return {"ok": True}


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_preflight_rejects_ring_policy_violation(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    toolbox = _NoOpToolbox()
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "compatibility",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                    }
                },
            },
            issue=None,
        )

    assert "E_RING_POLICY_VIOLATION" in str(exc.value)
    assert toolbox.calls == 0


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_preflight_rejects_capability_violation(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    toolbox = _NoOpToolbox()
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "skill_contract_enforced": True,
                "allowed_capability_profiles": ["workspace"],
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "workspace",
                        "capability_profile": "external",
                    }
                },
            },
            issue=None,
        )

    assert "E_CAPABILITY_VIOLATION" in str(exc.value)
    assert toolbox.calls == 0


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_emits_determinism_violation_for_declared_pure_side_effect_tool(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    toolbox = _NoOpToolbox()
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "pure",
                        "capability_profile": "workspace",
                    }
                },
            },
            issue=None,
        )

    assert "E_DETERMINISM_VIOLATION" in str(exc.value)
    assert toolbox.calls == 1
