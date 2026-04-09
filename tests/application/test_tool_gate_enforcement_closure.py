from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.application.middleware import TurnLifecycleInterceptors
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_tool_dispatcher import ToolDispatcher
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.extensions.contracts import RunAction
from orket.extensions.runtime import ExtensionEngineAdapter, RunContext
from orket.runtime.execution.execution_pipeline_card_dispatch import ExecutionPipelineCardDispatchMixin
from orket.schema import CardStatus, IssueConfig, RoleConfig


class _DenyAllToolGate(ToolGate):
    def __init__(self, workspace_root: Path, *, reason: str = "deny_all:write_file") -> None:
        super().__init__(organization=None, workspace_root=workspace_root)
        self.reason = reason

    async def validate(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any],
        roles: list[str],
    ) -> str | None:
        _ = args, context, roles
        return f"{self.reason}:{tool_name}"


class _WritingToolbox:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls = 0

    async def execute(self, tool_name: str, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        self.calls += 1
        target = Path(str(args["path"]))
        if not target.is_absolute():
            target = self.workspace_root / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(args.get("content", "")), encoding="utf-8")
        return {"ok": True, "tool": tool_name, "path": str(target)}


class _Model:
    def __init__(self, tool_name: str, tool_args: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.tool_args = dict(tool_args)

    async def complete(self, _messages: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "content": (
                '{"tool": "'
                + self.tool_name
                + '", "args": '
                + json.dumps(self.tool_args)
                + "}"
            ),
            "raw": {"total_tokens": 1},
        }


class _RunCardHarness(ExecutionPipelineCardDispatchMixin):
    def __init__(self, workspace_root: Path, tool_gate: ToolGate, tool_args: dict[str, Any]) -> None:
        self.workspace = workspace_root
        self._tool_gate = tool_gate
        self._tool_args = dict(tool_args)
        self.toolbox = _WritingToolbox(workspace_root)
        self.last_result = None

    async def initialize(self) -> None:
        return None

    async def _find_parent_epic(self, issue_id: str) -> tuple[Any, str | None, Any]:
        _ = issue_id
        return object(), "demo-epic", object()

    async def _resolve_run_card_target(self, card_id: str) -> tuple[str, str | None]:
        _ = card_id
        return "issue", "demo-epic"

    async def _run_epic_collection_entry(
        self,
        collection_name: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        raise AssertionError(f"Unexpected epic collection entry: {collection_name}")

    async def _run_issue_entry(
        self,
        issue_id: str,
        build_id: str | None = None,
        session_id: str | None = None,
        driver_steered: bool = False,
        parent_epic_name: str | None = None,
        target_issue_id: str | None = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        _ = build_id, session_id, driver_steered, parent_epic_name, target_issue_id, model_override
        self.last_result = await _execute_turn(
            workspace_root=self.workspace,
            tool_gate=self._tool_gate,
            tool_args=self._tool_args,
            toolbox=self.toolbox,
            issue_id=issue_id,
        )
        return {
            "success": self.last_result.success,
            "error": self.last_result.error,
            "violations": list(self.last_result.violations),
        }


def _context(issue_id: str) -> dict[str, Any]:
    return {
        "session_id": "sess-1",
        "issue_id": issue_id,
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy-model",
        "turn_index": 1,
        "history": [],
    }


def _issue(issue_id: str) -> IssueConfig:
    return IssueConfig(id=issue_id, summary="Implement feature", seat="developer", status=CardStatus.IN_PROGRESS)


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


async def _execute_turn(
    *,
    workspace_root: Path,
    tool_gate: ToolGate,
    tool_args: dict[str, Any],
    toolbox: _WritingToolbox,
    issue_id: str,
) -> Any:
    executor = TurnExecutor(
        state_machine=StateMachine(),
        tool_gate=tool_gate,
        workspace=workspace_root,
        middleware=TurnLifecycleInterceptors([]),
    )
    return await executor.execute_turn(
        _issue(issue_id),
        _role(),
        _Model("write_file", tool_args),
        toolbox,
        _context(issue_id),
    )


def _build_dispatcher(tmp_path: Path, tool_gate: ToolGate | None) -> ToolDispatcher:
    def _load_replay_tool_result(**_kwargs: Any) -> dict[str, Any] | None:
        return None

    def _persist_tool_result(**_kwargs: Any) -> None:
        return None

    def _load_operation_result(**_kwargs: Any) -> dict[str, Any] | None:
        return None

    def _persist_operation_result(**_kwargs: Any) -> None:
        return None

    def _append_protocol_receipt(**kwargs: Any) -> dict[str, Any]:
        return dict(kwargs.get("receipt") or {})

    return ToolDispatcher(
        tool_gate=tool_gate,  # type: ignore[arg-type]
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


def test_turn_executor_requires_tool_gate_at_construction(tmp_path: Path) -> None:
    """Layer: contract. Verifies the canonical turn executor path fails closed when tool-gate authority is missing."""
    with pytest.raises(TypeError, match="tool_gate authority"):
        TurnExecutor(
            state_machine=StateMachine(),
            tool_gate=None,  # type: ignore[arg-type]
            workspace=tmp_path,
        )


def test_tool_dispatcher_requires_tool_gate_at_construction(tmp_path: Path) -> None:
    """Layer: contract. Verifies the dispatcher seam fails closed before tool execution can start without a gate."""
    with pytest.raises(TypeError, match="tool_gate authority"):
        _build_dispatcher(tmp_path, None)


@pytest.mark.asyncio
async def test_run_card_primary_path_blocks_before_tool_execution(tmp_path: Path) -> None:
    """Layer: integration. Verifies the canonical run_card path blocks all tool execution under a deny-all gate."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    harness = _RunCardHarness(
        workspace_root=workspace_root,
        tool_gate=_DenyAllToolGate(workspace_root),
        tool_args={"path": "agent_output/denied.txt", "content": "x"},
    )

    result = await harness.run_card("ISSUE-1")

    assert result["success"] is False
    assert harness.toolbox.calls == 0
    assert not (workspace_root / "agent_output" / "denied.txt").exists()
    assert "deny_all:write_file:write_file" in str(result["error"])


@pytest.mark.asyncio
async def test_extension_action_primary_path_reenters_run_card_under_same_deny_all_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Layer: integration. Verifies normalized extension run actions re-enter the canonical blocked run_card path."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    harness = _RunCardHarness(
        workspace_root=workspace_root,
        tool_gate=_DenyAllToolGate(workspace_root),
        tool_args={"path": "agent_output/extension-denied.txt", "content": "x"},
    )

    class _EngineProxy:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        async def run_card(self, card_id: str, **kwargs: Any) -> dict[str, Any]:
            _ = kwargs
            return await harness.run_card(card_id)

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", _EngineProxy)

    adapter = ExtensionEngineAdapter(RunContext(workspace=workspace_root, department="core"))
    result = await adapter.execute_action(
        RunAction(op="run_issue", target="ISSUE-9", params={"session_id": "sess-1"})
    )

    assert result["transcript"]["success"] is False
    assert harness.toolbox.calls == 0
    assert not (workspace_root / "agent_output" / "extension-denied.txt").exists()
    assert "deny_all:write_file:write_file" in str(result["transcript"]["error"])


@pytest.mark.asyncio
async def test_canonical_dispatcher_blocks_write_escape_without_outside_side_effect(tmp_path: Path) -> None:
    """Layer: integration. Verifies blocked write escapes leave no file outside workspace_root on the canonical path."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    outside_path = tmp_path / "outside.txt"
    toolbox = _WritingToolbox(workspace_root)

    result = await _execute_turn(
        workspace_root=workspace_root,
        tool_gate=ToolGate(organization=None, workspace_root=workspace_root),
        tool_args={"path": "../outside.txt", "content": "escape"},
        toolbox=toolbox,
        issue_id="ISSUE-1",
    )

    assert result.success is False
    assert toolbox.calls == 0
    assert not outside_path.exists()
    assert "outside workspace" in str(result.error).lower()


@pytest.mark.asyncio
async def test_direct_tool_dispatcher_internal_seam_blocks_under_same_deny_all_policy(tmp_path: Path) -> None:
    """Layer: integration. Verifies the internal dispatcher seam still blocks before execution under the deny-all gate."""
    dispatcher = _build_dispatcher(tmp_path, _DenyAllToolGate(tmp_path))
    toolbox = _WritingToolbox(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/direct.txt", "content": "x"})],
    )

    with pytest.raises(RuntimeError, match="deny_all:write_file:write_file"):
        await dispatcher.execute_tools(
            turn=turn,
            toolbox=toolbox,
            context=_context("ISSUE-1"),
            issue=None,
        )

    assert toolbox.calls == 0
    assert not (tmp_path / "agent_output" / "direct.txt").exists()
