from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.policies.tool_gate import ToolGate


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
async def test_tool_dispatcher_preflight_rejects_namespace_scope_violation(tmp_path: Path) -> None:
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
                "allowed_namespace_scopes": ["issue:ISSUE-1"],
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                        "namespace_scope_rule": "declared_scope_subset",
                        "declared_namespace_scopes": ["issue:OTHER-1"],
                    }
                },
            },
            issue=None,
        )

    assert "E_NAMESPACE_POLICY_VIOLATION" in str(exc.value)
    assert toolbox.calls == 0


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_preflight_rejects_ring_policy_violation_without_protocol_governance(
    tmp_path: Path,
) -> None:
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
async def test_tool_dispatcher_preflight_rejects_namespace_scope_violation_without_protocol_governance(
    tmp_path: Path,
) -> None:
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
                "allowed_namespace_scopes": ["issue:ISSUE-1"],
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                        "namespace_scope_rule": "declared_scope_subset",
                        "declared_namespace_scopes": ["issue:OTHER-1"],
                    }
                },
            },
            issue=None,
        )

    assert "E_NAMESPACE_POLICY_VIOLATION" in str(exc.value)
    assert toolbox.calls == 0


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_preflight_rejects_missing_compatibility_mapping(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    toolbox = _NoOpToolbox()
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="openclaw.file_read", args={"path": "a.txt"})],
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
                "allowed_tool_rings": ["core", "compatibility"],
                "skill_tool_bindings": {
                    "openclaw.file_read": {
                        "entrypoint_id": "openclaw.file_read",
                        "ring": "compatibility",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                    }
                },
            },
            issue=None,
        )

    assert "E_COMPAT_MAPPING_MISSING" in str(exc.value)
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


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_preflight_rejects_tool_invocation_boundary_violation(tmp_path: Path) -> None:
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
                "invoked_from_tool": True,
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                    }
                },
            },
            issue=None,
        )

    assert "E_TOOL_INVOCATION_BOUNDARY" in str(exc.value)
    assert toolbox.calls == 0


# Layer: contract
@pytest.mark.asyncio
async def test_tool_dispatcher_records_determinism_violation_event(tmp_path: Path, monkeypatch) -> None:
    from orket.application.workflows import turn_tool_dispatcher as dispatcher_module

    events: list[dict[str, Any]] = []

    def _capture(event_name: str, payload: dict[str, Any], workspace: Path) -> None:
        events.append({"event": event_name, "payload": dict(payload), "workspace": str(workspace)})

    monkeypatch.setattr(dispatcher_module, "log_event", _capture)

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
    emitted = [entry for entry in events if entry.get("event") == "determinism_violation"]
    assert emitted
    payload = dict(emitted[0].get("payload") or {})
    assert payload["error_code"] == "E_DETERMINISM_VIOLATION"
    assert payload["determinism_class"] == "pure"
    assert payload["capability_profile"] == "workspace"
    assert payload["tool_contract_version"] == "1.0.0"
    assert "tool_name_side_effect" in list(payload.get("side_effect_signal_keys") or [])
    assert "E_DETERMINISM_VIOLATION" in str(payload.get("error", ""))


# Layer: contract
@pytest.mark.asyncio
async def test_tool_dispatcher_records_preflight_boundary_rejection_as_runtime_event(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from orket.application.workflows import turn_tool_dispatcher as dispatcher_module

    events: list[dict[str, Any]] = []

    def _capture(event_name: str, payload: dict[str, Any], workspace: Path) -> None:
        events.append({"event": event_name, "payload": dict(payload), "workspace": str(workspace)})

    monkeypatch.setattr(dispatcher_module, "log_event", _capture)

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
                "invoked_from_tool": True,
                "skill_contract_enforced": True,
                "skill_tool_bindings": {
                    "write_file": {
                        "entrypoint_id": "write_file",
                        "ring": "core",
                        "determinism_class": "workspace",
                        "capability_profile": "workspace",
                    }
                },
            },
            issue=None,
        )

    assert "E_TOOL_INVOCATION_BOUNDARY" in str(exc.value)
    emitted = [entry for entry in events if entry.get("event") == "tool_call_exception"]
    assert emitted
    assert emitted[0]["payload"]["tool"] == "write_file"
    assert "E_TOOL_INVOCATION_BOUNDARY" in str(emitted[0]["payload"]["error"])
    assert toolbox.calls == 0
