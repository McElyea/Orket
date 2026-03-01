from __future__ import annotations

from pathlib import Path

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.policies.tool_gate import ToolGate


def _dispatcher(tmp_path: Path) -> ToolDispatcher:
    return ToolDispatcher(
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        middleware=TurnLifecycleInterceptors([]),
        workspace=tmp_path,
        append_memory_event=lambda *args, **kwargs: None,
        hash_payload=lambda payload: "hash",
        load_replay_tool_result=lambda **kwargs: None,
        persist_tool_result=lambda **kwargs: None,
        tool_validation_error_factory=lambda violations: RuntimeError(str(violations)),
    )


def test_tool_dispatcher_permission_and_runtime_validation(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    binding = {
        "required_permissions": {"filesystem": ["read", "write"]},
        "runtime_limits": {"max_execution_time": 10, "max_memory": 256},
    }
    context = {
        "granted_permissions": {"filesystem": ["read"]},
        "max_tool_execution_time": 5,
        "max_tool_memory": 128,
    }
    missing = dispatcher.missing_required_permissions(binding, context)
    limits = dispatcher.runtime_limit_violations(binding, context)
    assert "filesystem:write" in missing
    assert sorted(limits) == ["max_execution_time", "max_memory"]


def test_tool_dispatcher_skill_binding_resolution(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    context = {"skill_tool_bindings": {"write_file": {"entrypoint_id": "write-main"}}}
    assert dispatcher.resolve_skill_tool_binding(context, "write_file") == {"entrypoint_id": "write-main"}
    assert dispatcher.resolve_skill_tool_binding(context, "read_file") is None
