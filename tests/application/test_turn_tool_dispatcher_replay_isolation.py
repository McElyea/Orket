from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.protocol_hashing import build_step_id, derive_operation_id
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.policies.tool_gate import ToolGate


def _make_dispatcher(
    tmp_path: Path,
    *,
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]],
    persist_operation_calls: list[dict[str, Any]],
    persist_tool_calls: list[dict[str, Any]],
    receipt_rows: list[dict[str, Any]],
) -> ToolDispatcher:
    def _load_replay_tool_result(**_kwargs) -> dict[str, Any] | None:
        return None

    def _persist_tool_result(**kwargs) -> None:
        persist_tool_calls.append(dict(kwargs))

    def _load_operation_result(**kwargs) -> dict[str, Any] | None:
        key = (
            str(kwargs.get("session_id")),
            str(kwargs.get("issue_id")),
            str(kwargs.get("role_name")),
            int(kwargs.get("turn_index", 0)),
            str(kwargs.get("operation_id")),
        )
        return operation_store.get(key)

    def _persist_operation_result(**kwargs) -> None:
        persist_operation_calls.append(dict(kwargs))

    def _append_protocol_receipt(**kwargs) -> dict[str, Any]:
        row = dict(kwargs.get("receipt") or {})
        receipt_rows.append(row)
        return row

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
        return {"ok": True, "executed": True}


# Layer: integration
@pytest.mark.asyncio
async def test_replay_mode_with_protocol_enabled_skips_persistence_side_effects(tmp_path: Path) -> None:
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    persist_operation_calls: list[dict[str, Any]] = []
    persist_tool_calls: list[dict[str, Any]] = []
    receipt_rows: list[dict[str, Any]] = []
    dispatcher = _make_dispatcher(
        tmp_path,
        operation_store=operation_store,
        persist_operation_calls=persist_operation_calls,
        persist_tool_calls=persist_tool_calls,
        receipt_rows=receipt_rows,
    )

    session_id = "s1"
    issue_id = "ISSUE-1"
    role_name = "coder"
    turn_index = 1
    step_id = build_step_id(issue_id=issue_id, turn_index=turn_index)
    operation_id = derive_operation_id(run_id=session_id, step_id=step_id, tool_index=0)
    operation_store[(session_id, issue_id, role_name, turn_index, operation_id)] = {
        "operation_id": operation_id,
        "result": {"ok": True, "source": "recorded"},
        "tool": "write_file",
        "args": {"path": "a.txt", "content": "x"},
    }

    turn = ExecutionTurn(
        role=role_name,
        issue_id=issue_id,
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )
    toolbox = _NoOpToolbox()
    await dispatcher.execute_tools(
        turn=turn,
        toolbox=toolbox,
        context={
            "roles": [role_name],
            "session_id": session_id,
            "turn_index": turn_index,
            "protocol_governed_enabled": True,
            "protocol_replay_mode": True,
        },
        issue=None,
    )

    assert toolbox.calls == 0
    assert turn.tool_calls[0].result == {"ok": True, "source": "recorded"}
    assert persist_operation_calls == []
    assert persist_tool_calls == []
    assert receipt_rows == []


# Layer: integration
@pytest.mark.asyncio
async def test_replay_mode_with_protocol_disabled_skips_legacy_tool_result_persist(tmp_path: Path) -> None:
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    persist_operation_calls: list[dict[str, Any]] = []
    persist_tool_calls: list[dict[str, Any]] = []
    receipt_rows: list[dict[str, Any]] = []
    dispatcher = _make_dispatcher(
        tmp_path,
        operation_store=operation_store,
        persist_operation_calls=persist_operation_calls,
        persist_tool_calls=persist_tool_calls,
        receipt_rows=receipt_rows,
    )

    session_id = "s1"
    issue_id = "ISSUE-1"
    role_name = "coder"
    turn_index = 1
    step_id = build_step_id(issue_id=issue_id, turn_index=turn_index)
    operation_id = derive_operation_id(run_id=session_id, step_id=step_id, tool_index=0)
    operation_store[(session_id, issue_id, role_name, turn_index, operation_id)] = {
        "operation_id": operation_id,
        "result": {"ok": True, "source": "recorded"},
        "tool": "write_file",
        "args": {"path": "a.txt", "content": "x"},
    }

    turn = ExecutionTurn(
        role=role_name,
        issue_id=issue_id,
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )
    toolbox = _NoOpToolbox()
    await dispatcher.execute_tools(
        turn=turn,
        toolbox=toolbox,
        context={
            "roles": [role_name],
            "session_id": session_id,
            "turn_index": turn_index,
            "protocol_governed_enabled": False,
            "protocol_replay_mode": True,
        },
        issue=None,
    )

    assert toolbox.calls == 0
    assert turn.tool_calls[0].result == {"ok": True, "source": "recorded"}
    assert persist_operation_calls == []
    assert persist_tool_calls == []
    assert receipt_rows == []
