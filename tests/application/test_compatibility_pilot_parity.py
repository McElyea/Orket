from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.policies.tool_gate import ToolGate


def _dispatcher(
    tmp_path: Path,
    *,
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] | None = None,
) -> ToolDispatcher:
    operation_store = operation_store if operation_store is not None else {}

    def _load_replay_tool_result(**_kwargs) -> dict[str, Any] | None:
        return None

    def _persist_tool_result(**_kwargs) -> None:
        return None

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
        key = (
            str(kwargs.get("session_id")),
            str(kwargs.get("issue_id")),
            str(kwargs.get("role_name")),
            int(kwargs.get("turn_index", 0)),
            str(kwargs.get("operation_id")),
        )
        operation_store[key] = {
            "operation_id": str(kwargs.get("operation_id") or ""),
            "result": dict(kwargs.get("result") or {}),
        }

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


class _PilotToolbox:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, tool_name, args, context):
        _ = (args, context)
        self.calls.append(str(tool_name))
        if tool_name == "workspace.read":
            return {"ok": True, "content": "alpha"}
        if tool_name == "workspace.list":
            return {"ok": True, "items": ["a.txt"]}
        if tool_name == "workspace.search":
            return {"ok": True, "matches": [{"path": "a.txt"}]}
        if tool_name == "file.patch":
            return {"ok": True, "patched": 1}
        return {"ok": False, "error": f"unknown_tool:{tool_name}"}


# Layer: integration
@pytest.mark.asyncio
async def test_compatibility_pilot_live_and_replay_parity(tmp_path: Path) -> None:
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    dispatcher = _dispatcher(tmp_path, operation_store=operation_store)
    toolbox = _PilotToolbox()
    base_context = {
        "roles": ["coder"],
        "session_id": "pilot-run-1",
        "protocol_governed_enabled": True,
        "skill_contract_enforced": True,
        "allowed_tool_rings": ["core", "compatibility"],
        "compatibility_mappings": {
            "openclaw.file_read": {
                "mapping_version": 1,
                "mapped_core_tools": ["workspace.read"],
                "schema_compatibility_range": ">=1.0.0 <2.0.0",
                "determinism_class": "workspace",
            },
            "openclaw.workspace_list": {
                "mapping_version": 1,
                "mapped_core_tools": ["workspace.list"],
                "schema_compatibility_range": ">=1.0.0 <2.0.0",
                "determinism_class": "workspace",
            },
            "openclaw.file_edit": {
                "mapping_version": 1,
                "mapped_core_tools": ["workspace.search", "file.patch"],
                "schema_compatibility_range": ">=1.0.0 <2.0.0",
                "determinism_class": "workspace",
            },
        },
        "skill_tool_bindings": {
            "openclaw.file_read": {"entrypoint_id": "openclaw.file_read", "ring": "compatibility", "determinism_class": "workspace", "capability_profile": "workspace"},
            "openclaw.workspace_list": {"entrypoint_id": "openclaw.workspace_list", "ring": "compatibility", "determinism_class": "workspace", "capability_profile": "workspace"},
            "openclaw.file_edit": {"entrypoint_id": "openclaw.file_edit", "ring": "compatibility", "determinism_class": "workspace", "capability_profile": "workspace"},
            "workspace.read": {"entrypoint_id": "workspace.read", "ring": "core", "determinism_class": "workspace", "capability_profile": "workspace"},
            "workspace.list": {"entrypoint_id": "workspace.list", "ring": "core", "determinism_class": "workspace", "capability_profile": "workspace"},
            "workspace.search": {"entrypoint_id": "workspace.search", "ring": "core", "determinism_class": "workspace", "capability_profile": "workspace"},
            "file.patch": {"entrypoint_id": "file.patch", "ring": "core", "determinism_class": "workspace", "capability_profile": "workspace"},
        },
    }
    pilot_calls = [
        ("openclaw.file_read", {"path": "a.txt"}),
        ("openclaw.workspace_list", {"path": "."}),
        ("openclaw.file_edit", {"path": "a.txt", "content": "beta"}),
    ]
    live_results: list[dict[str, Any]] = []

    for turn_index, (tool_name, tool_args) in enumerate(pilot_calls, start=1):
        turn = ExecutionTurn(
            role="coder",
            issue_id="ISSUE-PILOT",
            content="",
            tool_calls=[ToolCall(tool=tool_name, args=tool_args)],
        )
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={**base_context, "turn_index": turn_index},
            issue=None,
        )
        result = dict(turn.tool_calls[0].result or {})
        live_results.append(result)
        translation = result.get("compat_translation")
        assert isinstance(translation, dict)
        assert translation["mapping_version"] == 1
        assert translation["mapping_determinism"] == "workspace"
        assert int(translation.get("latency_ms", 0)) >= 0

    live_call_count = len(toolbox.calls)
    assert live_call_count >= 4

    for turn_index, (tool_name, tool_args) in enumerate(pilot_calls, start=1):
        turn = ExecutionTurn(
            role="coder",
            issue_id="ISSUE-PILOT",
            content="",
            tool_calls=[ToolCall(tool=tool_name, args=tool_args)],
        )
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={**base_context, "turn_index": turn_index, "protocol_replay_mode": True},
            issue=None,
        )
        assert dict(turn.tool_calls[0].result or {}) == live_results[turn_index - 1]

    assert len(toolbox.calls) == live_call_count
