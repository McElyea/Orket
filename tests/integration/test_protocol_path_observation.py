"""Layer: integration. Protocol path-observation responsiveness controls.

Required-read classification and submitted tool-path validation are separate
boundaries. Each tool retains its policy, compatibility, workspace, gate, skill and
approval ordering. These controls establish responsiveness, not cancellation lifetime.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiosqlite
import pytest

from orket.application.workflows.turn_tool_dispatcher_protocol import (
    collect_protocol_preflight_violations,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATH = "agent_output/input.txt"


class _RecordingGate:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], tuple[str, ...]]] = []

    async def validate(self, tool_name, args, context, roles):
        self.calls.append((tool_name, dict(args), tuple(roles)))
        return None


def _turn(path: str) -> ExecutionTurn:
    return ExecutionTurn(
        timestamp=None,
        role="reviewer",
        issue_id="ISSUE-PATH",
        content="",
        tool_calls=[ToolCall(tool="read_file", args={"path": path})],
    )


async def _collect(*, turn, context, gate, workspace, binding=None) -> list[str]:
    return await collect_protocol_preflight_violations(
        turn=turn,
        context=context,
        roles=["reviewer"],
        approval_required_tools=set(),
        tool_gate=gate,
        workspace=workspace,
        resolve_skill_tool_binding=lambda _context, _tool: binding,
        missing_required_permissions=lambda _binding, _context: [],
        runtime_limit_violations=lambda _binding, _context: [],
    )


def _hold_first_resolve(monkeypatch, target: Path, *, enabled: bool):
    state = SimpleNamespace(
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        threads=[],
        timers=[],
    )
    original = Path.resolve

    def observed(path, *args, **kwargs):
        if enabled and Path(path) == target and not state.entered.is_set():
            state.threads.append(threading.get_ident())
            state.entered.set()
            timer = threading.Timer(0.8, state.release.set)
            state.timers.append(timer)
            timer.start()
            try:
                assert state.release.wait(5), "Native path observation was not released"
                return original(path, *args, **kwargs)
            finally:
                state.finished.set()
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", observed)
    return state


async def _sqlite_elapsed(database: Path, started: float) -> float:
    async with aiosqlite.connect(database) as connection:
        await connection.execute("CREATE TABLE response_probe (value INTEGER)")
        await connection.execute("INSERT INTO response_probe VALUES (42)")
        await connection.commit()
        assert await (await connection.execute("SELECT value FROM response_probe")).fetchone() == (42,)
    return time.perf_counter() - started


async def _write_bytes(path: Path, content: bytes) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, content)


async def _settle(tasks, state, target: Path, expected: bytes) -> None:
    errors: list[BaseException] = []
    state.release.set()
    for timer in state.timers:
        timer.cancel()
        try:
            await asyncio.to_thread(timer.join, 5)
        except BaseException as error:
            errors.append(error)
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
    except BaseException as error:
        errors.append(error)
    if state.entered.is_set():
        try:
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            errors.append(error)
    try:
        assert all(not timer.is_alive() for timer in state.timers)
        assert await asyncio.to_thread(target.read_bytes) == expected
    except BaseException as error:
        errors.append(error)
    if errors:
        first, *rest = errors
        for error in rest:
            first.add_note(f"Additional cleanup failure: {error!r}")
        raise first


async def _run_responsiveness_case(
    *, tmp_path: Path, monkeypatch, record_property, required_paths: list[str], held: bool,
) -> None:
    workspace = tmp_path / "workspace"
    target, expected = workspace / _READ_PATH, b"real protocol input\n"
    await _write_bytes(target, expected)
    state = _hold_first_resolve(monkeypatch, target, enabled=held)
    gate = _RecordingGate()
    context = {"required_action_tools": ["read_file"], "required_read_paths": required_paths}
    started = time.perf_counter()
    operation = asyncio.create_task(
        _collect(turn=_turn(_READ_PATH), context=context, gate=gate, workspace=workspace)
    )
    probe = asyncio.create_task(_sqlite_elapsed(tmp_path / "responsive.sqlite3", started))
    primary_error: BaseException | None = None
    try:
        violations, elapsed = await asyncio.wait_for(asyncio.gather(operation, probe), 5)
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < 0.5
        assert violations == []
        assert gate.calls == [("read_file", {"path": _READ_PATH}, ("reviewer",))]
        if held:
            assert state.entered.is_set() and state.finished.is_set()
            assert state.threads == [state.threads[0]]
            assert state.threads[0] != threading.get_ident()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle([operation, probe], state, target, expected)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Path-observation cleanup also failed: {cleanup_error!r}")


@pytest.mark.parametrize("held", [False, True], ids=["healthy", "native-hold"])
async def test_required_read_classification_keeps_event_loop_responsive(
    tmp_path: Path, monkeypatch, record_property, held: bool,
) -> None:
    await _run_responsiveness_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        record_property=record_property,
        required_paths=[_READ_PATH],
        held=held,
    )


@pytest.mark.parametrize("held", [False, True], ids=["healthy", "native-hold"])
async def test_submitted_tool_path_validation_keeps_event_loop_responsive(
    tmp_path: Path, monkeypatch, record_property, held: bool,
) -> None:
    await _run_responsiveness_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        record_property=record_property,
        required_paths=[],
        held=held,
    )


@pytest.mark.parametrize(
    ("case", "detail"),
    [("traversal", "path_traversal"), ("absolute", "absolute_path")],
)
async def test_escaping_declared_path_still_uses_submitted_path_refusal(
    tmp_path: Path, case: str, detail: str,
) -> None:
    workspace, outside = tmp_path / "workspace", tmp_path / "outside.txt"
    expected = b"outside bytes remain unchanged\n"
    await _write_bytes(outside, expected)
    await asyncio.to_thread(workspace.mkdir)
    token = "../outside.txt" if case == "traversal" else str(await asyncio.to_thread(outside.resolve))
    gate = _RecordingGate()
    try:
        violations = await _collect(
            turn=_turn(token),
            context={"required_action_tools": ["read_file"], "required_read_paths": [token]},
            gate=gate,
            workspace=workspace,
        )
        assert violations == [f"E_WORKSPACE_CONSTRAINT:read_file:{detail}"]
        assert gate.calls == []
    finally:
        assert await asyncio.to_thread(outside.read_bytes) == expected


async def test_symlink_escape_declared_path_still_uses_submitted_path_refusal(tmp_path: Path) -> None:
    workspace, outside = tmp_path / "workspace", tmp_path / "outside"
    target, link = outside / "secret.txt", workspace / "escape"
    expected = b"symlink target remains unchanged\n"
    await _write_bytes(target, expected)
    await asyncio.to_thread(workspace.mkdir)
    try:
        await asyncio.to_thread(link.symlink_to, outside, target_is_directory=True)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"directory symlink unavailable on this host: {error}")
    token, gate = "escape/secret.txt", _RecordingGate()
    try:
        violations = await _collect(
            turn=_turn(token),
            context={"required_action_tools": ["read_file"], "required_read_paths": [token]},
            gate=gate,
            workspace=workspace,
        )
        assert violations == ["E_WORKSPACE_CONSTRAINT:read_file:path_escape"]
        assert gate.calls == []
    finally:
        assert await asyncio.to_thread(target.read_bytes) == expected
