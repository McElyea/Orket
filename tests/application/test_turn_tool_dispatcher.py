from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn, ToolCall


def _dispatcher(
    tmp_path: Path,
    *,
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] | None = None,
    replay_store: dict[tuple[str, str], dict[str, Any]] | None = None,
    receipt_rows: list[dict[str, Any]] | None = None,
    middleware: TurnLifecycleInterceptors | None = None,
) -> ToolDispatcher:
    operation_store = operation_store if operation_store is not None else {}
    replay_store = replay_store if replay_store is not None else {}
    receipt_rows = receipt_rows if receipt_rows is not None else []

    def _load_replay_tool_result(**kwargs) -> dict[str, Any] | None:
        key = (str(kwargs.get("tool_name")), str(kwargs.get("tool_args")))
        return replay_store.get(key)

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
            "operation_id": str(kwargs.get("operation_id")),
            "result": dict(kwargs.get("result") or {}),
            "tool": str(kwargs.get("tool_name") or ""),
            "args": dict(kwargs.get("tool_args") or {}),
        }

    def _append_protocol_receipt(**kwargs) -> dict[str, Any]:
        row = dict(kwargs.get("receipt") or {})
        receipt_rows.append(row)
        return row

    return ToolDispatcher(
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        middleware=middleware or TurnLifecycleInterceptors([]),
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


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_blocks_execution(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"}),
            ToolCall(tool="read_file", args={"path": "a.txt"}),
        ],
    )

    class _Toolbox:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, tool_name, args, context):
            self.calls += 1
            return {"ok": True}

    toolbox = _Toolbox()
    with pytest.raises(RuntimeError):
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "approval_required_tools": ["write_file"],
            },
            issue=None,
        )
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_enforces_max_tool_calls(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"}),
            ToolCall(tool="read_file", args={"path": "a.txt"}),
        ],
    )

    class _Toolbox:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, tool_name, args, context):
            self.calls += 1
            return {"ok": True}

    toolbox = _Toolbox()
    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "max_tool_calls": 1,
            },
            issue=None,
        )
    assert "E_MAX_TOOL_CALLS" in str(exc.value)
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_enforces_required_tool_presence(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="read_file", args={"path": "a.txt"})],
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=_Toolbox(),
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "required_action_tools": ["write_file"],
            },
            issue=None,
        )
    assert "E_MISSING_REQUIRED_TOOL:write_file" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_enforces_required_sequence(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"}),
            ToolCall(tool="read_file", args={"path": "a.txt"}),
        ],
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=_Toolbox(),
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "required_sequence": ["read_file", "write_file"],
            },
            issue=None,
        )
    assert "E_TOOL_SEQUENCE" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_enforces_workspace_constraints(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "../escape.txt", "content": "x"})],
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=_Toolbox(),
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
            },
            issue=None,
        )
    assert "E_WORKSPACE_CONSTRAINT:write_file:path_traversal" in str(exc.value)


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_preflight_is_fail_fast(tmp_path: Path) -> None:
    dispatcher = _dispatcher(tmp_path)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[
            ToolCall(tool="", args={"path": "../escape.txt", "content": "x"}),
            ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"}),
        ],
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=_Toolbox(),
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
                "protocol_governed_enabled": True,
                "required_action_tools": ["write_file"],
            },
            issue=None,
        )
    message = str(exc.value)
    assert "E_SCHEMA_TOOL_CALL:0:tool" in message
    assert "E_MISSING_REQUIRED_TOOL" not in message


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_operation_idempotency_reuses_cached_result(tmp_path: Path) -> None:
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    receipt_rows: list[dict[str, Any]] = []
    dispatcher = _dispatcher(tmp_path, operation_store=operation_store, receipt_rows=receipt_rows)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )

    class _Toolbox:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, tool_name, args, context):
            self.calls += 1
            return {"ok": True, "call_count": self.calls}

    toolbox = _Toolbox()
    context = {
        "roles": ["coder"],
        "session_id": "s1",
        "turn_index": 1,
        "protocol_governed_enabled": True,
    }

    await dispatcher.execute_tools(turn=turn, toolbox=toolbox, context=context, issue=None)
    assert toolbox.calls == 1
    assert isinstance(turn.tool_calls[0].result, dict)
    assert turn.tool_calls[0].result.get("call_count") == 1

    second_turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )
    await dispatcher.execute_tools(turn=second_turn, toolbox=toolbox, context=context, issue=None)
    assert toolbox.calls == 1
    assert second_turn.tool_calls[0].result == {"ok": True, "call_count": 1}
    assert len(receipt_rows) == 2


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_treats_non_dict_middleware_result_as_explicit_failure(tmp_path: Path) -> None:
    class _BadAfterTool:
        def after_tool(self, tool_name, args, result, *, issue, role_name, context):
            return MiddlewareOutcome(replacement="broken-result")

    dispatcher = _dispatcher(
        tmp_path,
        middleware=TurnLifecycleInterceptors([_BadAfterTool()]),
    )
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    with pytest.raises(RuntimeError) as exc:
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=_Toolbox(),
            context={
                "roles": ["coder"],
                "session_id": "s1",
                "turn_index": 1,
            },
            issue=None,
        )

    assert "non-dict result (str)" in str(exc.value)
    assert turn.tool_calls[0].result == {
        "ok": False,
        "error": "tool middleware returned non-dict result (str)",
    }


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_replay_mode_uses_operation_record_and_skips_execution(tmp_path: Path) -> None:
    operation_store: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    dispatcher = _dispatcher(tmp_path, operation_store=operation_store)

    class _Toolbox:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, tool_name, args, context):
            self.calls += 1
            return {"ok": True, "call_count": self.calls}

    toolbox = _Toolbox()
    context = {
        "roles": ["coder"],
        "session_id": "s1",
        "turn_index": 1,
        "protocol_governed_enabled": True,
    }
    live_turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )
    await dispatcher.execute_tools(turn=live_turn, toolbox=toolbox, context=context, issue=None)
    assert toolbox.calls == 1

    replay_turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
    )
    await dispatcher.execute_tools(
        turn=replay_turn,
        toolbox=toolbox,
        context={**context, "protocol_replay_mode": True},
        issue=None,
    )
    assert toolbox.calls == 1
    assert replay_turn.tool_calls[0].result == {"ok": True, "call_count": 1}


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_replay_mode_missing_operation_fails_closed(tmp_path: Path) -> None:
    replay_store = {
        ("write_file", str({"path": "a.txt", "content": "x"})): {"ok": True, "source": "legacy-replay-store"},
    }
    dispatcher = _dispatcher(tmp_path, replay_store=replay_store)

    class _Toolbox:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, tool_name, args, context):
            self.calls += 1
            return {"ok": True}

    toolbox = _Toolbox()
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
                "protocol_replay_mode": True,
            },
            issue=None,
        )
    assert "E_REPLAY_OPERATION_MISSING" in str(exc.value)
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_tool_dispatcher_protocol_receipt_uses_turn_raw_metadata(tmp_path: Path) -> None:
    receipt_rows: list[dict[str, Any]] = []
    dispatcher = _dispatcher(tmp_path, receipt_rows=receipt_rows)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "x"})],
        raw={
            "proposal_hash": "a" * 64,
            "validator_version": "turn-validator/custom",
            "protocol_hash": "b" * 64,
            "tool_schema_hash": "c" * 64,
        },
    )

    class _Toolbox:
        async def execute(self, tool_name, args, context):
            return {"ok": True}

    await dispatcher.execute_tools(
        turn=turn,
        toolbox=_Toolbox(),
        context={
            "roles": ["coder"],
            "session_id": "s1",
            "turn_index": 1,
            "protocol_governed_enabled": True,
            "network_mode": "allowlist",
            "network_allowlist_values": ["api.example.com"],
            "clock_mode": "artifact_replay",
            "clock_artifact_ref": "artifacts/clock/run-a.json",
            "timezone": "UTC",
            "locale": "C.UTF-8",
            "env_allowlist": {"HOME": "/home/user"},
        },
        issue=None,
    )
    assert len(receipt_rows) == 1
    row = receipt_rows[0]
    assert row["proposal_hash"] == "a" * 64
    assert row["validator_version"] == "turn-validator/custom"
    assert row["protocol_hash"] == "b" * 64
    assert row["tool_schema_hash"] == "c" * 64
    manifest = row["tool_invocation_manifest"]
    assert manifest["run_id"] == "s1"
    assert manifest["tool_name"] == "write_file"
    assert len(str(manifest["manifest_hash"])) == 64
    assert len(str(row["tool_call_hash"])) == 64
    capsule = row["execution_capsule"]
    assert capsule["network_mode"] == "allowlist"
    assert capsule["clock_mode"] == "artifact_replay"
    assert capsule["clock_artifact_ref"] == "artifacts/clock/run-a.json"
    assert len(capsule["network_allowlist_hash"]) == 64
    assert len(capsule["clock_artifact_hash"]) == 64
    assert len(capsule["env_allowlist_hash"]) == 64


# Layer: integration
@pytest.mark.asyncio
async def test_tool_dispatcher_executes_compatibility_mapping_and_records_translation(tmp_path: Path) -> None:
    receipt_rows: list[dict[str, Any]] = []
    dispatcher = _dispatcher(tmp_path, receipt_rows=receipt_rows)
    turn = ExecutionTurn(
        role="coder",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="openclaw.file_read", args={"path": "a.txt"})],
    )

    class _Toolbox:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def execute(self, tool_name, args, context):
            self.calls.append(str(tool_name))
            if tool_name == "workspace.read":
                return {"ok": True, "content": "alpha"}
            return {"ok": False, "error": f"unexpected:{tool_name}"}

    toolbox = _Toolbox()
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
                },
                "workspace.read": {
                    "entrypoint_id": "workspace.read",
                    "ring": "core",
                    "determinism_class": "workspace",
                    "capability_profile": "workspace",
                },
            },
            "compatibility_mappings": {
                "openclaw.file_read": {
                    "mapping_version": 1,
                    "mapped_core_tools": ["workspace.read"],
                    "schema_compatibility_range": ">=1.0.0 <2.0.0",
                    "determinism_class": "workspace",
                }
            },
        },
        issue=None,
    )

    assert toolbox.calls == ["workspace.read"]
    result = turn.tool_calls[0].result
    assert isinstance(result, dict)
    assert result.get("ok") is True
    assert isinstance(result.get("compat_translation"), dict)
    assert result["compat_translation"]["compat_tool_name"] == "openclaw.file_read"
    assert len(receipt_rows) == 1
    assert isinstance(receipt_rows[0].get("compat_translation"), dict)
