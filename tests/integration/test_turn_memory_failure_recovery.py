"""Layer: integration. Composed turn memory failure and recovery ownership controls.

These cases use a controlled model and physical files. They do not establish
provider acceptance, atomic publication, hostile-filesystem confinement, or a
hard native deadline.
"""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import (
    build_turn_tool_control_plane_service,
)
from orket.application.workflows.turn_executor import TurnExecutor, TurnResult
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.helpers.turn_control_plane_clock import (
    deterministic_turn_clock as deterministic_turn_clock,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("deterministic_turn_clock"),
]
_RUN_ID = "turn-tool-run:run-1:ISSUE-1:developer:0001"


class _Model:
    def __init__(self, *, failure: bool = False) -> None:
        self.calls = 0
        self.failure = failure

    async def complete(self, _messages):
        self.calls += 1
        if self.failure:
            raise RuntimeError("controlled model failure")
        return {
            "content": (
                '{"content":"","tool_calls":[{"tool":"write_file",'
                '"args":{"path":"agent_output/out.txt","content":"ok"}}]}'
            ),
            "raw": {"total_tokens": 1},
        }


class _Toolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        return {"ok": True, "tool": tool_name, "touched_paths": [args["path"]]}


class _BeforePromptFailure:
    def before_prompt(self, _messages, **_kwargs):
        return MiddlewareOutcome(short_circuit=True, reason="controlled before-prompt failure")


def _issue() -> IssueConfig:
    return IssueConfig(
        id="ISSUE-1", summary="Memory recovery", seat="developer",
        status=CardStatus.IN_PROGRESS,
    )


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


def _context(*, replay: bool = False) -> dict[str, object]:
    return {
        "session_id": "run-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "controlled-model",
        "turn_index": 1,
        "history": [],
        "resume_mode": replay,
        "protocol_governed_enabled": True,
        "visibility_mode": "read_only",
        "memory_snapshot_id": "snapshot-1",
        "max_turn_retries": 0,
    }


def _build(tmp_path: Path, *, model_failure: bool = False, before_prompt: bool = False):
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    middleware = TurnLifecycleInterceptors([_BeforePromptFailure()]) if before_prompt else None
    executor = TurnExecutor(
        StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
        workspace=tmp_path, middleware=middleware, control_plane_service=control_plane,
        utc_now=artifact_test_utc_now,
    )
    return executor, control_plane, _Model(failure=model_failure), _Toolbox()


def _paths(tmp_path: Path) -> dict[str, Path]:
    root = tmp_path / "observability" / "run-1" / "issue-1" / "001_developer"
    return {
        "memory": root / "memory_trace.json",
        "retrieval": root / "memory_retrieval_trace.json",
        "response_text": root / "model_response.txt",
        "response_raw": root / "model_response_raw.json",
    }


def _install_held_fault(
    monkeypatch, executor: TurnExecutor, target: Path, *, fault_calls: set[int],
):
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        target_calls=0, memory_attempts=0, fault_types=[], threads=[], writes=[],
    )
    original_write = Path.write_text
    original_memory = executor.artifact_writer.write_memory_trace_publication

    def counted_memory(*, destination, publication):
        state.memory_attempts += 1
        return original_memory(destination=destination, publication=publication)

    def held_write(path, *args, **kwargs):
        state.writes.append(path)
        if path != target:
            return original_write(path, *args, **kwargs)
        state.target_calls += 1
        call = state.target_calls
        state.threads.append(threading.get_ident())
        if call == 1:
            state.entered.set()
            assert state.release.wait(5), "Native composed artifact write was not released"
        try:
            if call in fault_calls:
                path.mkdir()
                try:
                    return original_write(path, *args, **kwargs)
                except OSError as error:
                    state.fault_types.append(type(error).__name__)
                    path.rmdir()
                    raise
            return original_write(path, *args, **kwargs)
        finally:
            if call == 1:
                state.finished.set()

    monkeypatch.setattr(executor.artifact_writer, "write_memory_trace_publication", counted_memory)
    monkeypatch.setattr(Path, "write_text", held_write)
    return state


async def _remove(paths: list[Path]) -> None:
    for path in paths:
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)


async def _read_json(path: Path) -> dict:
    return json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8"))


async def _drive(
    *, executor: TurnExecutor, model: _Model, toolbox: _Toolbox, context: dict[str, object],
    state, stop: str, sqlite_path: Path, record_property,
):
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await executor.execute_turn(_issue(), _role(), model, toolbox, context, "SYSTEM")

    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.threads and state.threads[0] != threading.get_ident()
        await responsive_sqlite(sqlite_path, record_property)
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        elif stop == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        if stop != "none":
            await asyncio.sleep(.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        return (await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5))[0]
    finally:
        state.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)


async def _seed_replay(executor, model, toolbox, paths) -> None:
    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(), "SYSTEM")
    assert first.success is True
    await _remove([paths["memory"], paths["retrieval"]])


@pytest.mark.parametrize("route", ["normal", "replay"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.parametrize("late_fault", [False, True], ids=["clean", "late-oserror"])
async def test_terminal_memory_publication_preserves_recovery_ceiling(
    tmp_path, monkeypatch, record_property, route, stop, late_fault,
):
    executor, control_plane, model, toolbox = _build(tmp_path)
    paths = _paths(tmp_path)
    if route == "replay":
        await _seed_replay(executor, model, toolbox, paths)
    state = _install_held_fault(
        monkeypatch, executor, paths["retrieval"], fault_calls={1} if late_fault else set(),
    )
    outcome = await _drive(
        executor=executor, model=model, toolbox=toolbox, context=_context(replay=route == "replay"),
        state=state, stop=stop, sqlite_path=tmp_path / "responsive.sqlite3",
        record_property=record_property,
    )
    trace = await _read_json(paths["memory"])
    assert await asyncio.to_thread(paths["retrieval"].is_file)
    failure_events = [row for row in trace["events"] if row["interceptor"] == "on_turn_failure"]
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=_RUN_ID)

    if late_fault:
        assert isinstance(outcome, TurnResult) and outcome.success is False
        assert state.memory_attempts == 2
        assert len(state.fault_types) == 1
        assert len(failure_events) == 1
        assert failure_events[0]["decision_type"] == state.fault_types[0]
        assert trace["output"]["output_type"] == "error"
    else:
        expected = asyncio.CancelledError if stop == "cancel" else TimeoutError
        assert isinstance(outcome, expected)
        assert state.memory_attempts == 1
        assert failure_events == []
        assert trace["output"]["output_type"] == "text"
    assert state.target_calls == state.memory_attempts
    assert state.writes.count(paths["memory"]) == state.memory_attempts
    assert len(attempts) == 1
    assert model.calls == 1
    assert toolbox.calls == 1
    record_property("composed_memory_terminal", json.dumps({
        "route": route, "stop": stop, "late_fault": late_fault,
        "memory_attempts": state.memory_attempts, "fault_types": state.fault_types,
        "failure_events": failure_events, "control_plane_attempts": len(attempts),
    }, sort_keys=True))


async def test_failure_recovery_second_publication_error_escapes_without_third(
    tmp_path, monkeypatch, record_property,
):
    executor, _control_plane, model, toolbox = _build(tmp_path)
    paths = _paths(tmp_path)
    state = _install_held_fault(monkeypatch, executor, paths["retrieval"], fault_calls={1, 2})
    outcome = await _drive(
        executor=executor, model=model, toolbox=toolbox, context=_context(), state=state,
        stop="cancel", sqlite_path=tmp_path / "responsive.sqlite3", record_property=record_property,
    )
    trace = await _read_json(paths["memory"])

    assert isinstance(outcome, OSError)
    assert state.memory_attempts == state.target_calls == 2
    assert state.writes.count(paths["memory"]) == 2
    assert len(state.fault_types) == 2
    assert trace["events"][-1]["decision_type"] == state.fault_types[0]
    assert not await asyncio.to_thread(paths["retrieval"].exists)
    record_property("composed_memory_double_failure", json.dumps({
        "memory_attempts": state.memory_attempts, "fault_types": state.fault_types,
        "retrieval_path": str(paths["retrieval"]),
    }, sort_keys=True))


@pytest.mark.parametrize("route", ["established-handler", "early-helper"])
async def test_failure_publication_errors_keep_existing_handler_order(
    tmp_path, monkeypatch, record_property, route,
):
    executor, _control_plane, model, toolbox = _build(
        tmp_path, model_failure=route == "established-handler", before_prompt=route == "early-helper",
    )
    paths = _paths(tmp_path)
    state = _install_held_fault(monkeypatch, executor, paths["retrieval"], fault_calls={1})
    outcome = await _drive(
        executor=executor, model=model, toolbox=toolbox, context=_context(), state=state,
        stop="none", sqlite_path=tmp_path / "responsive.sqlite3", record_property=record_property,
    )
    trace = await _read_json(paths["memory"])
    decisions = [row["decision_type"] for row in trace["events"] if row["interceptor"] == "on_turn_failure"]

    if route == "established-handler":
        assert isinstance(outcome, OSError)
        assert state.memory_attempts == 1
        assert decisions == ["RuntimeError"]
        assert not await asyncio.to_thread(paths["retrieval"].exists)
    else:
        assert isinstance(outcome, TurnResult) and outcome.success is False
        assert state.memory_attempts == 2
        assert decisions == ["before_prompt_short_circuit", state.fault_types[0]]
        assert await asyncio.to_thread(paths["retrieval"].is_file)
    assert state.target_calls == state.memory_attempts
    assert state.writes.count(paths["memory"]) == state.memory_attempts
    record_property("composed_memory_handler", json.dumps({
        "route": route, "memory_attempts": state.memory_attempts,
        "fault_types": state.fault_types, "decisions": decisions,
    }, sort_keys=True))


@pytest.mark.parametrize("late_fault", [False, True], ids=["clean-cancel", "late-oserror"])
async def test_response_publication_only_enters_failure_memory_on_late_error(
    tmp_path, monkeypatch, record_property, late_fault,
):
    executor, _control_plane, model, toolbox = _build(tmp_path)
    paths = _paths(tmp_path)
    state = _install_held_fault(
        monkeypatch, executor, paths["response_raw"], fault_calls={1} if late_fault else set(),
    )
    outcome = await _drive(
        executor=executor, model=model, toolbox=toolbox, context=_context(), state=state,
        stop="cancel", sqlite_path=tmp_path / "responsive.sqlite3", record_property=record_property,
    )
    memory_exists = await asyncio.to_thread(paths["memory"].exists)
    assert await asyncio.to_thread(paths["response_text"].is_file)
    if late_fault:
        trace = await _read_json(paths["memory"])
        assert isinstance(outcome, TurnResult) and outcome.success is False
        assert state.memory_attempts == 1 and memory_exists
        assert len(state.fault_types) == 1
        assert trace["events"][-1]["decision_type"] == state.fault_types[0]
        assert await asyncio.to_thread(paths["retrieval"].is_file)
        assert not await asyncio.to_thread(paths["response_raw"].exists)
    else:
        assert isinstance(outcome, asyncio.CancelledError)
        assert state.memory_attempts == 0 and not memory_exists
        assert await asyncio.to_thread(paths["response_raw"].is_file)
    assert state.writes.count(paths["memory"]) == state.memory_attempts
    record_property("composed_response_failure_boundary", json.dumps({
        "late_fault": late_fault, "memory_attempts": state.memory_attempts,
        "fault_types": state.fault_types, "response_raw": str(paths["response_raw"]),
        "memory_exists": memory_exists,
    }, sort_keys=True))
