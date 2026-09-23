"""Validation/corrective ownership of required-read observations.

Layer labels are per test because this module includes pure contract controls and
real composed integration paths.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_corrective_prompt import CorrectivePromptBuilder
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_read_context import RequiredReadObservation
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from orket.schema import IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import interrupt_owned, responsive_sqlite

_A = "agent_output/a.txt"
_B = "agent_output/b.txt"
_OUT = "agent_output/out.txt"


def _role() -> RoleConfig:
    return RoleConfig(
        id="DEV", summary="developer", description="Build", tools=["read_file", "write_file"]
    )


def _turn(path: str, *, partial: bool = False) -> ExecutionTurn:
    return ExecutionTurn(
        timestamp=None,
        role="developer",
        issue_id="ISSUE-READ",
        tool_calls=[ToolCall(tool="read_file", args={"path": path})],
        partial_parse_failure=partial,
        error="partial" if partial else None,
    )


def _context(path: str) -> dict[str, object]:
    return {
        "session_id": "read-owner",
        "issue_id": "ISSUE-READ",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "fixture",
        "turn_index": 1,
        "history": [],
        "required_action_tools": ["read_file", "write_file"],
        "required_read_paths": [path],
    }


class _Model:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    async def complete(self, messages):
        self.messages.append([dict(item) for item in messages])
        output = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return {"content": output, "raw": {"total_tokens": 1}}


class _Toolbox:
    def __init__(self, root: Path) -> None:
        self.files = AsyncFileTools(root)
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.read_results: list[str] = []

    async def execute(self, tool_name, args, _context):
        self.calls.append((tool_name, dict(args)))
        if tool_name == "read_file":
            content = await self.files.read_file(args["path"])
            self.read_results.append(content)
            return {"ok": True, "content": content}
        assert tool_name == "write_file"
        return {"ok": True, "path": await self.files.write_file(args["path"], args["content"])}


def _payload(read_path: str) -> str:
    return (
        '{"content":"","tool_calls":['
        f'{{"tool":"read_file","args":{{"path":"{read_path}"}}}},'
        '{"tool":"write_file","args":{"path":"agent_output/out.txt","content":"ok"}}]}'
    )


def _hold_validation_resolve(monkeypatch, target: Path, model: _Model, *, fail: bool = False):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    original = Path.resolve

    def held(path, *args, **kwargs):
        if model.calls == 1 and Path(path) == target and not state.entered.is_set():
            state.entered.set()
            try:
                assert state.release.wait(5)
                if fail:
                    raise OSError("late required-read metadata failure")
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", held)
    return state


async def _settle_held_task(task, state, expected: tuple[tuple[Path, bytes], ...]) -> None:
    if not task.done():
        task.cancel()
    state.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    if state.entered.is_set():
        assert await asyncio.to_thread(state.finished.wait, 5)
    assert await asyncio.gather(
        *(asyncio.to_thread(path.read_bytes) for path, _content in expected)
    ) == [content for _path, content in expected]


def _executor(root: Path) -> TurnExecutor:
    return TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root), workspace=root)


def test_validator_and_corrective_are_pure_after_explicit_observation(tmp_path, monkeypatch) -> None:
    """Layer: contract. Explicit classification removes filesystem access from both consumers."""
    monkeypatch.setattr(Path, "resolve", lambda *_args, **_kwargs: pytest.fail("unexpected metadata"))
    observation = RequiredReadObservation(existing=(_A, _B), missing=())
    context = _context(_A)
    context["required_read_paths"] = [_A, _B]
    validator = ContractValidator(ResponseParser(tmp_path, lambda **_kwargs: None))

    violations = validator.collect_contract_violations(_turn(_A), _role(), context, observation)
    prompt = CorrectivePromptBuilder().build_corrective_instruction(violations, context, observation)

    read_failure = next(item for item in violations if item["reason"] == "read_path_contract_not_met")
    assert read_failure["required_read_paths"] == [_A, _B]
    assert f"  - {_A}" in prompt and f"  - {_B}" in prompt


@pytest.mark.asyncio
async def test_partial_parse_keeps_validation_metadata_free(tmp_path, monkeypatch) -> None:
    """Layer: contract. The attempt coordinator returns partial diagnostics without observation."""
    from orket.application.workflows import turn_contract_input_capture as capture_owner

    async def unexpected_observation(**_kwargs):
        pytest.fail("partial validation admitted required-read metadata")

    monkeypatch.setattr(capture_owner, "observe_legacy_required_read_paths", unexpected_observation)
    validator = ContractValidator(ResponseParser(tmp_path, lambda **_kwargs: None))
    attempt, violations = await capture_owner.collect_validation_attempt(
        validator=validator, turn=_turn(_A, partial=True), role=_role(),
        context=_context(_A), workspace=tmp_path,
    )

    assert attempt.required_read_observation is None
    assert [item["reason"] for item in violations] == ["partial_parse_failure"]


@pytest.mark.asyncio
async def test_composed_validation_executes_captured_turn(tmp_path, monkeypatch, record_property) -> None:
    """Layer: integration. Mutation during metadata cannot change the validated or dispatched command."""
    root = tmp_path / "workspace"
    a_path, b_path = root / _A, root / _B
    await asyncio.to_thread(a_path.parent.mkdir, parents=True)
    await asyncio.to_thread(a_path.write_bytes, b"a\n")
    await asyncio.to_thread(b_path.write_bytes, b"b\n")
    model, toolbox, executor = _Model([_payload(_A)]), _Toolbox(root), _executor(root)
    role, context = _role(), _context(_A)
    parsed: list[ExecutionTurn] = []
    parse = executor.response_parser.parse_response

    def record_parse(**kwargs):
        value = parse(**kwargs)
        parsed.append(value)
        return value

    monkeypatch.setattr(executor.response_parser, "parse_response", record_parse)
    state = _hold_validation_resolve(monkeypatch, a_path, model)
    operation = asyncio.create_task(
        executor.execute_turn(IssueConfig(id="ISSUE-READ", summary="Read", seat="developer", status="in_progress"),
                              role, model, toolbox, context)
    )
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "captured.sqlite3", record_property)
        parsed[0].tool_calls[0].args["path"] = _B
        role.tools[:] = ["update_issue_status"]
        state.release.set()
        result = await asyncio.wait_for(operation, 5)

        assert result.success and result.turn is not parsed[0]
        assert model.calls == 1
        assert result.turn.tool_calls[0].args == {"path": _A}
        assert toolbox.calls[0] == ("read_file", {"path": _A})
        assert result.turn.tool_calls[0].result == {"ok": True, "content": "a\n"}
        assert toolbox.read_results == ["a\n"]
        assert await asyncio.to_thread((root / _OUT).read_bytes) == b"ok"
        assert parsed[0].tool_calls[0].args == {"path": _B}
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_held_task(operation, state, ((a_path, b"a\n"), (b_path, b"b\n")))
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Validation capture cleanup failed: {cleanup_error!r}")


@pytest.mark.asyncio
async def test_corrective_reuses_initial_observation_and_retry_observes_fresh_state(
    tmp_path, monkeypatch, record_property,
) -> None:
    """Layer: integration. Corrective A stays consistent while retry validation uses fresh B."""
    root = tmp_path / "workspace"
    a_path, b_path = root / _A, root / _B
    await asyncio.to_thread(a_path.parent.mkdir, parents=True)
    await asyncio.to_thread(a_path.write_bytes, b"a\n")
    await asyncio.to_thread(b_path.write_bytes, b"b\n")
    model = _Model([_payload("agent_output/wrong.txt"), _payload(_B)])
    toolbox, executor, context = _Toolbox(root), _executor(root), _context(_A)
    state = _hold_validation_resolve(monkeypatch, a_path, model)
    operation = asyncio.create_task(
        executor.execute_turn(IssueConfig(id="ISSUE-READ", summary="Read", seat="developer", status="in_progress"),
                              _role(), model, toolbox, context)
    )
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "retry.sqlite3", record_property)
        context["required_read_paths"] = [_B]
        state.release.set()
        result = await asyncio.wait_for(operation, 5)

        corrective = model.messages[1][-1]["content"]
        assert result.success and result.turn.tool_calls[0].args == {"path": _B}
        assert f"  - {_A}" in corrective and f"  - {_B}" not in corrective
        assert toolbox.calls[0] == ("read_file", {"path": _B})
        assert result.turn.tool_calls[0].result == {"ok": True, "content": "b\n"}
        assert toolbox.read_results == ["b\n"]
        assert await asyncio.to_thread((root / _OUT).read_bytes) == b"ok"
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_held_task(operation, state, ((a_path, b"a\n"), (b_path, b"b\n")))
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Corrective capture cleanup failed: {cleanup_error!r}")


@pytest.mark.asyncio
@pytest.mark.parametrize("timed", [False, True], ids=["repeated-cancel", "timeout"])
async def test_validation_late_native_failure_settles_before_return(
    tmp_path, monkeypatch, record_property, timed,
) -> None:
    """Layer: integration. The composed route drains metadata and keeps its late failure."""
    root, target = tmp_path / "workspace", tmp_path / "workspace" / _A
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    await asyncio.to_thread(target.write_bytes, b"unchanged\n")
    model, toolbox, executor = _Model([_payload(_A)]), _Toolbox(root), _executor(root)
    state = _hold_validation_resolve(monkeypatch, target, model, fail=True)
    validator_calls: list[bool] = []
    collect = executor.contract_validator.collect_contract_violations

    def record_validation(*args):
        validator_calls.append(True)
        return collect(*args)

    monkeypatch.setattr(executor.contract_validator, "collect_contract_violations", record_validation)
    task = asyncio.create_task(executor.execute_turn(
        IssueConfig(id="ISSUE-READ", summary="Read", seat="developer", status="in_progress"),
        _role(), model, toolbox, _context(_A),
    ))
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / f"interrupt-{timed}.sqlite3", record_property)
        waiter = await interrupt_owned(task, state.release, timed=timed)
        result = await waiter
        assert result.success is False and "late required-read metadata failure" in result.error
        assert state.finished.is_set() and validator_calls == []
        assert toolbox.calls == []
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_held_task(task, state, ((target, b"unchanged\n"),))
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Validation interruption cleanup failed: {cleanup_error!r}")
