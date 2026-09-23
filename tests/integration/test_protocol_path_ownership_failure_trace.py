"""Layer: integration. Captured protocol turns remain the failure-trace authority."""

from __future__ import annotations

import asyncio
import copy
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from orket.naming import sanitize_name
from orket.schema import IssueConfig, RoleConfig
from tests.helpers.turn_artifacts import artifact_test_utc_now, execute_executor_dispatch_fixture

_A = "agent_output/a.txt"
_B = "agent_output/b.txt"


class _Model:
    async def complete(self, _messages):
        return {
            "content": (
                '{"content":"","tool_calls":['
                f'{{"tool":"read_file","args":{{"path":"{_A}"}}}},'
                '{"tool":"write_file","args":'
                '{"path":"agent_output/out.txt","content":"ok"}}]}'
            ),
            "raw": {"total_tokens": 1},
        }


class _FailingToolbox:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, tool_name, args, _context):
        self.calls.append((tool_name, dict(args)))
        return {"ok": False, "error": f"{tool_name} refused"}


class _CancelledToolbox:
    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    async def execute(self, tool_name, args, context):
        self.calls.append((tool_name, dict(args), context))
        if len(self.calls) == 1:
            return {"ok": True, "index": 1}
        self.entered.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def _context() -> dict[str, Any]:
    return {
        "session_id": "failure-capture",
        "issue_id": "ISSUE-PROTOCOL-FAILURE",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "fixture",
        "turn_index": 1,
        "history": [],
        "memory_trace_enabled": True,
        "protocol_governed_enabled": True,
        "required_action_tools": ["write_file"],
        "required_write_paths": ["agent_output/out.txt"],
    }


def _hold_submitted_path(monkeypatch, target: Path):
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
    )
    original = Path.resolve

    def held(path, *args, **kwargs):
        if Path(path) == target and not state.entered.is_set():
            state.entered.set()
            try:
                assert state.release.wait(5)
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", held)
    return state


async def _assert_published_trace(root: Path) -> None:
    path = (
        root / "observability" / sanitize_name("failure-capture")
        / sanitize_name("ISSUE-PROTOCOL-FAILURE") / "001_developer/memory_trace.json"
    )
    trace = json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))
    traced_paths = [
        call["normalized_args"].get("path")
        for event in trace["events"] for call in event["tool_calls"]
        if call["tool_name"] in {"read_file", "write_file"}
    ]
    assert _A in traced_paths and _B not in traced_paths
    assert trace["events"][-1]["decision_type"] == "tool_violation"


async def test_dispatch_failure_trace_uses_captured_turn(tmp_path, monkeypatch) -> None:
    """Caller mutation during preflight cannot replace failure or memory-trace inputs."""
    root, toolbox = tmp_path / "workspace", _FailingToolbox()
    a_path, b_path = root / _A, root / _B
    await asyncio.to_thread(a_path.parent.mkdir, parents=True)
    await asyncio.to_thread(a_path.write_bytes, b"a unchanged\n")
    await asyncio.to_thread(b_path.write_bytes, b"b unchanged\n")
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root, utc_now=artifact_test_utc_now)
    dispatched: list[ExecutionTurn] = []
    traced: list[ExecutionTurn] = []
    dispatch = executor.tool_dispatcher.execute_tools
    from orket.application.workflows import turn_failure_traces
    render_memory_traces = turn_failure_traces.render_memory_trace_publication

    async def record_dispatch(**kwargs):
        dispatched.append(kwargs["turn"])
        return await dispatch(**kwargs)

    def record_memory_trace(**kwargs):
        traced.append(kwargs["turn"])
        return render_memory_traces(**kwargs)

    monkeypatch.setattr(executor.tool_dispatcher, "execute_tools", record_dispatch)
    monkeypatch.setattr(turn_failure_traces, "render_memory_trace_publication", record_memory_trace)
    state = _hold_submitted_path(monkeypatch, a_path)
    operation = asyncio.create_task(executor.execute_turn(
        IssueConfig(id="ISSUE-PROTOCOL-FAILURE", summary="Failure", seat="developer", status="in_progress"),
        RoleConfig(id="DEV", summary="developer", description="Build", tools=["read_file", "write_file"]),
        _Model(), toolbox, _context(),
    ))
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        expected_raw = copy.deepcopy(dispatched[0].raw)
        dispatched[0].content = "mutated caller content"
        dispatched[0].raw = {"mutated": True}
        dispatched[0].tool_calls[0].args["path"] = _B
        state.release.set()
        result = await asyncio.wait_for(operation, 5)

        failure_turn = traced[0]
        assert result.success is False
        assert failure_turn is not dispatched[0]
        assert failure_turn.content == "" and failure_turn.raw == expected_raw
        assert failure_turn.tool_calls[0].args == {"path": _A}
        assert toolbox.calls[0] == ("read_file", {"path": _A})
        assert dispatched[0].tool_calls[0].result == failure_turn.tool_calls[0].result
        await _assert_published_trace(root)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if not operation.done():
            operation.cancel()
        state.release.set()
        try:
            await asyncio.wait_for(asyncio.gather(operation, return_exceptions=True), 5)
            if state.entered.is_set():
                assert await asyncio.to_thread(state.finished.wait, 5)
            assert await asyncio.gather(
                asyncio.to_thread(a_path.read_bytes), asyncio.to_thread(b_path.read_bytes)
            ) == [b"a unchanged\n", b"b unchanged\n"]
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Failure-trace cleanup failed: {cleanup_error!r}")


async def test_dispatch_cancellation_publishes_completed_original_sink(tmp_path) -> None:
    """Cancellation adopts the captured turn and publishes each completed original sink."""
    root = tmp_path / "workspace"
    target = root / _A
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    await asyncio.to_thread(target.write_bytes, b"a unchanged\n")
    await asyncio.to_thread((root / _B).write_bytes, b"b unchanged\n")
    toolbox = _CancelledToolbox()
    turn = ExecutionTurn(
        timestamp=None, role="developer", issue_id="ISSUE-PROTOCOL",
        tool_calls=[
            ToolCall(tool="read_file", args={"path": _A}),
            ToolCall(tool="read_file", args={"path": _B}),
        ],
    )
    originals, adopted = tuple(turn.tool_calls), []
    context = {
        "roles": ["developer"], "session_id": "dispatch-cancel", "turn_index": 1,
        "protocol_governed_enabled": True,
    }
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root, utc_now=artifact_test_utc_now)
    task = asyncio.create_task(
        execute_executor_dispatch_fixture(executor,
            turn=turn, toolbox=toolbox, context=context,
            on_turn_captured=adopted.append,
        )
    )
    primary_error: BaseException | None = None
    try:
        await asyncio.wait_for(toolbox.entered.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert originals[0].result == {"ok": True, "index": 1}
        assert len(adopted) == 1 and adopted[0] is not turn
        assert originals[0].error is None and originals[0].error_class is None
        assert originals[1].result is None and originals[1].error is None
        assert originals[1].error_class is None
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            if not task.done():
                task.cancel()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert await asyncio.gather(
                asyncio.to_thread(target.read_bytes), asyncio.to_thread((root / _B).read_bytes)
            ) == [b"a unchanged\n", b"b unchanged\n"]
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Dispatch cancellation cleanup failed: {cleanup_error!r}")
