"""Layer: integration. Protocol metadata order, lifetime and dispatch binding."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows import turn_tool_dispatcher_protocol as protocol_owner
from orket.application.workflows.turn_executor import ToolValidationError, TurnExecutor
from orket.application.workflows.turn_tool_dispatcher_protocol import collect_protocol_preflight_violations
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from tests.helpers.kernel_state_probe import interrupt_owned, responsive_sqlite
from tests.helpers.turn_artifacts import artifact_test_utc_now, execute_executor_dispatch_fixture

_A = "agent_output/a.txt"
_B = "agent_output/b.txt"


class _Gate:
    def __init__(self, *, refusal: str | None = None) -> None:
        self.refusal = refusal
        self.calls: list[tuple[str, dict[str, Any], tuple[str, ...]]] = []

    async def validate(self, tool_name, args, context, roles):
        self.calls.append((tool_name, dict(args), tuple(roles)))
        return self.refusal


def _turn(*calls: tuple[str, dict[str, Any]]) -> ExecutionTurn:
    return ExecutionTurn(
        timestamp=None, role="developer", issue_id="ISSUE-PROTOCOL",
        tool_calls=[ToolCall(tool=tool, args=args) for tool, args in calls],
    )


async def _collect(*, turn, context, gate, workspace, approvals=frozenset(), binding=None):
    return await collect_protocol_preflight_violations(
        turn=turn,
        context=context,
        roles=["developer"],
        approval_required_tools=set(approvals),
        tool_gate=gate,
        workspace=workspace,
        resolve_skill_tool_binding=lambda _context, _tool: binding,
        missing_required_permissions=lambda _binding, _context: [],
        runtime_limit_violations=lambda _binding, _context: [],
    )


def _hold_resolve(monkeypatch, target: Path, *, fail: bool = False):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    original = Path.resolve

    def held(path, *args, **kwargs):
        if Path(path) == target and not state.entered.is_set():
            state.entered.set()
            try:
                assert state.release.wait(5)
                if fail:
                    raise OSError("late protocol metadata failure")
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", held)
    return state


async def _settle_task(task, state, expected: tuple[tuple[Path, bytes], ...]) -> None:
    if not task.done():
        task.cancel()
    state.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    if state.entered.is_set():
        assert await asyncio.to_thread(state.finished.wait, 5)
    assert await asyncio.gather(
        *(asyncio.to_thread(path.read_bytes) for path, _content in expected)
    ) == [content for _path, content in expected]


async def _files(root: Path) -> tuple[Path, Path, tuple[bytes, bytes]]:
    a_path, b_path = root / _A, root / _B
    await asyncio.to_thread(a_path.parent.mkdir, parents=True)
    await asyncio.to_thread(a_path.write_bytes, b"a unchanged\n")
    await asyncio.to_thread(b_path.write_bytes, b"b unchanged\n")
    return a_path, b_path, (b"a unchanged\n", b"b unchanged\n")


async def test_two_required_reads_preserve_cardinality(tmp_path) -> None:
    """Two existing declarations and one call refuse before gate admission."""
    root = tmp_path / "workspace"
    a_path, b_path, before = await _files(root)
    gate = _Gate()
    violations = await _collect(
        turn=_turn(("read_file", {"path": _A})),
        context={"required_action_tools": ["read_file"], "required_read_paths": [_A, _B]},
        gate=gate,
        workspace=root,
    )

    assert violations == ["E_TOOL_CARDINALITY:read_file:1"]
    assert gate.calls == []
    assert await asyncio.gather(
        asyncio.to_thread(a_path.read_bytes), asyncio.to_thread(b_path.read_bytes)
    ) == list(before)


async def test_protocol_preflight_preserves_exact_stage_order(tmp_path, monkeypatch) -> None:
    """Binding, policy, compatibility, workspace, gate, skill and approval retain order."""
    root = tmp_path / "workspace"
    await _files(root)
    order: list[str] = []
    policy, compatibility = protocol_owner.tool_policy_violation, protocol_owner.resolve_compatibility_translation
    workspace_observer = protocol_owner.observe_workspace_constraint_violation

    def binding(_context, _tool):
        order.append("binding")
        return {}

    def observed_policy(**kwargs):
        order.append("policy")
        return policy(**kwargs)

    def observed_compatibility(**kwargs):
        order.append("compatibility")
        return compatibility(**kwargs)

    async def observed_workspace(**kwargs):
        order.append("workspace")
        return await workspace_observer(**kwargs)

    class _OrderedGate(_Gate):
        async def validate(self, tool_name, args, context, roles):
            order.append("gate")
            return await super().validate(tool_name, args, context, roles)

    monkeypatch.setattr(protocol_owner, "tool_policy_violation", observed_policy)
    monkeypatch.setattr(protocol_owner, "resolve_compatibility_translation", observed_compatibility)
    monkeypatch.setattr(protocol_owner, "observe_workspace_constraint_violation", observed_workspace)
    violations = await collect_protocol_preflight_violations(
        turn=_turn(("read_file", {"path": _A})), context={"skill_contract_enforced": True},
        roles=["developer"], approval_required_tools={"read_file"}, tool_gate=_OrderedGate(),
        workspace=root, resolve_skill_tool_binding=binding,
        missing_required_permissions=lambda *_args: order.append("permissions") or [],
        runtime_limit_violations=lambda *_args: order.append("limits") or [],
    )

    assert violations == ["Approval required for tool 'read_file' before execution."]
    assert order == ["binding", "policy", "compatibility", "workspace", "gate", "permissions", "limits"]


async def test_earlier_gate_refusal_never_observes_later_tool_path(tmp_path, monkeypatch) -> None:
    """A refused earlier tool prevents admission of later submitted-path metadata."""
    root = tmp_path / "workspace"
    _a_path, b_path, _before = await _files(root)
    original = Path.resolve
    later_observed: list[Path] = []

    def observed(path, *args, **kwargs):
        if Path(path) == b_path:
            later_observed.append(Path(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", observed)
    gate = _Gate(refusal="first refused")
    violations = await _collect(
        turn=_turn(("add_issue_comment", {"comment": "stop"}), ("read_file", {"path": _B})),
        context={}, gate=gate, workspace=root,
    )

    assert violations == ["Governance Violation: first refused"]
    assert [call[0] for call in gate.calls] == ["add_issue_comment"]
    assert later_observed == []


async def test_relative_workspace_is_bound_before_gate_changes_cwd(tmp_path, monkeypatch) -> None:
    """A gate-time CWD change cannot rebind the second submitted path."""
    root = tmp_path / "workspace"
    a_path, b_path, before = await _files(root)
    elsewhere = tmp_path / "elsewhere"
    await asyncio.to_thread(elsewhere.mkdir)
    monkeypatch.chdir(tmp_path)

    class _ChangingGate(_Gate):
        async def validate(self, tool_name, args, context, roles):
            result = await super().validate(tool_name, args, context, roles)
            if len(self.calls) == 1:
                monkeypatch.chdir(elsewhere)
            return result

    gate = _ChangingGate()
    violations = await _collect(
        turn=_turn(("read_file", {"path": _A}), ("read_file", {"path": _B})),
        context={}, gate=gate, workspace=Path("workspace"),
    )

    assert violations == [] and [call[0] for call in gate.calls] == ["read_file", "read_file"]
    assert await asyncio.gather(
        asyncio.to_thread(a_path.read_bytes), asyncio.to_thread(b_path.read_bytes)
    ) == list(before)


@pytest.mark.parametrize("boundary", ["required", "submitted"])
@pytest.mark.parametrize("timed", [False, True], ids=["repeated-cancel", "timeout"])
async def test_protocol_metadata_failure_settles_before_interruption_returns(
    tmp_path, monkeypatch, record_property, boundary, timed,
) -> None:
    """Admitted native metadata drains, preserves late failure and skips later gate stages."""
    root = tmp_path / "workspace"
    a_path, _b_path, before = await _files(root)
    state, gate = _hold_resolve(monkeypatch, a_path, fail=True), _Gate()
    context = (
        {"required_action_tools": ["read_file"], "required_read_paths": [_A]}
        if boundary == "required" else {}
    )
    task = asyncio.create_task(_collect(
        turn=_turn(("read_file", {"path": _A})), context=context, gate=gate, workspace=root,
    ))
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / f"{boundary}-{timed}.sqlite3", record_property)
        waiter = await interrupt_owned(task, state.release, timed=timed)
        with pytest.raises(OSError, match="late protocol metadata failure"):
            await waiter
        assert state.finished.is_set() and gate.calls == []
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_task(task, state, ((a_path, before[0]),))
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Protocol interruption cleanup failed: {cleanup_error!r}")


class _Toolbox:
    def __init__(self, *, fail_second: bool = False) -> None:
        self.fail_second = fail_second
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    async def execute(self, tool_name, args, context):
        self.calls.append((tool_name, dict(args), context))
        if self.fail_second and len(self.calls) == 2:
            raise RuntimeError("second tool failed")
        return {"ok": True, "index": len(self.calls)}


def _executor(root: Path) -> TurnExecutor:
    return TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root, utc_now=artifact_test_utc_now)


def _dispatch_context(sentinel: object) -> dict[str, Any]:
    return {
        "roles": ["developer"], "session_id": "dispatch-capture", "turn_index": 1,
        "protocol_governed_enabled": True, "sentinel": sentinel,
        "approval_required_tools": [],
        "extension_dict_sink": {}, "extension_list_sink": [],
    }


async def test_dispatch_uses_captured_commands_and_publishes_original_sink(
    tmp_path, monkeypatch, record_property,
) -> None:
    """Mutation during preflight cannot alter dispatch; original result sink still receives the outcome."""
    root = tmp_path / "workspace"
    a_path, _b_path, before = await _files(root)
    state = _hold_resolve(monkeypatch, a_path)
    sentinel, replacement = object(), object()
    context, toolbox = _dispatch_context(sentinel), _Toolbox()
    extension_dict, extension_list = context["extension_dict_sink"], context["extension_list_sink"]
    completion_authority = object()

    def callback(**_kwargs):
        return None

    prompt_sink = {}
    context["create_pending_gate_request"], context["prompt_metadata"] = callback, prompt_sink
    context["card_completion_context"] = completion_authority
    turn = _turn(("read_file", {"path": _A}))
    original_call = turn.tool_calls[0]
    adopted: list[ExecutionTurn] = []
    operation = asyncio.create_task(
        execute_executor_dispatch_fixture(_executor(root),
            turn=turn, toolbox=toolbox, context=context, on_turn_captured=adopted.append,
        )
    )
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "dispatch.sqlite3", record_property)
        original_call.args["path"] = _B
        context["roles"].append("mutated")
        context["approval_required_tools"].append("read_file")
        context["sentinel"] = replacement
        state.release.set()
        captured_turn = await asyncio.wait_for(operation, 5)

        assert captured_turn is not turn and captured_turn.tool_calls[0].args == {"path": _A}
        assert adopted == [captured_turn]
        assert toolbox.calls[0][1] == {"path": _A} and toolbox.calls[0][2]["sentinel"] is sentinel
        assert toolbox.calls[0][2]["extension_dict_sink"] is extension_dict
        assert toolbox.calls[0][2]["extension_list_sink"] is extension_list
        assert toolbox.calls[0][2]["create_pending_gate_request"] is callback
        assert toolbox.calls[0][2]["prompt_metadata"] is prompt_sink
        assert toolbox.calls[0][2]["card_completion_context"] is completion_authority
        assert original_call.result is captured_turn.tool_calls[0].result
        assert original_call.error is None and original_call.error_class is None
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_task(operation, state, ((a_path, before[0]),))
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Dispatch capture cleanup failed: {cleanup_error!r}")


async def test_dispatch_failure_publishes_each_original_tool_sink(tmp_path) -> None:
    """A later execution failure retains earlier result and later error on original ToolCall objects."""
    root = tmp_path / "workspace"
    await _files(root)
    turn = _turn(("read_file", {"path": _A}), ("read_file", {"path": _B}))
    original_calls = tuple(turn.tool_calls)
    toolbox = _Toolbox(fail_second=True)
    adopted: list[ExecutionTurn] = []

    def adopt(captured: ExecutionTurn) -> None:
        adopted.append(captured)
        turn.content, turn.raw = "mutated", {"proposal_hash": "mutated"}
        original_calls[1].args["path"] = _A

    with pytest.raises(ToolValidationError, match="second tool failed"):
        await execute_executor_dispatch_fixture(_executor(root),
            turn=turn, toolbox=toolbox, context=_dispatch_context(object()), on_turn_captured=adopt,
        )

    assert adopted[0].content == "" and adopted[0].raw == {}
    assert adopted[0].tool_calls[1].args == {"path": _B}
    assert original_calls[0] is turn.tool_calls[0] and original_calls[0].result == {"ok": True, "index": 1}
    assert original_calls[0].error is None and original_calls[0].error_class is None
    assert original_calls[1] is turn.tool_calls[1] and original_calls[1].result is None
    assert original_calls[1].error == "second tool failed"
    assert original_calls[1].error_class.value == "execution_failed"
