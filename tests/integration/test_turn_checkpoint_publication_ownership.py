"""Layer: integration. Checkpoint publication owns each admitted native write."""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import write_checkpoint_fixture

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_NOW = datetime(2026, 9, 23, 19, 0, tzinfo=UTC)
_RUN_ID = "turn-tool-run:checkpoint-session:CHECKPOINT-1:developer:0002"


def _case(tmp_path: Path):
    service = build_turn_tool_control_plane_service(tmp_path / "control-plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(), ToolGate(organization=None, workspace_root=tmp_path), tmp_path,
        control_plane_service=service, utc_now=lambda: _NOW,
    )
    turn = ExecutionTurn(
        timestamp=None, role="developer", issue_id="CHECKPOINT-1", content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    context = {
        "session_id": "checkpoint-session", "issue_id": "CHECKPOINT-1", "role": "developer",
        "turn_index": 2, "protocol_governed_enabled": True, "run_namespace_scope": "issue:CHECKPOINT-1",
        "roles": ["developer"], "current_status": "in_progress", "selected_model": "controlled",
        "history": [], "resume_mode": False,
    }
    output = tmp_path / "observability/checkpoint-session/checkpoint-1/002_developer"
    return SimpleNamespace(service=service, executor=executor, turn=turn, context=context, output=output)


def _hold_write(monkeypatch, stage: str, fault: bool):
    original = Path.write_text
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            target=None, fault="", worker=None, calls=[])

    def held(path, *args, **kwargs):
        selected = path.name == "checkpoint.json" if stage == "local" else path.name.startswith(
            "control_plane_checkpoint_snapshot_")
        if not selected:
            return original(path, *args, **kwargs)
        state.target, state.worker = path, threading.get_ident()
        state.calls.append(str(path))
        state.entered.set()
        try:
            assert state.release.wait(5), "Native checkpoint write was not released"
            if fault:
                path.mkdir()
            return original(path, *args, **kwargs)
        except OSError as error:
            state.fault = type(error).__name__
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "write_text", held)
    return state


async def _interrupt(stop: str, task, deadline) -> None:
    if stop == "cancel":
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
    elif stop == "timeout":
        deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
    if stop != "none":
        await asyncio.sleep(0.03)


async def _settle(task, state, primary_error: BaseException | None) -> None:
    state.release.set()
    if not task.done():
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
    except BaseException as error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Checkpoint cleanup also failed: {error!r}")
    target = state.target
    if target is not None and await asyncio.to_thread(target.is_dir):
        await asyncio.to_thread(target.rmdir)


async def _observe(task, *, stop: str, fault: bool) -> None:
    if fault:
        with pytest.raises(OSError):
            await asyncio.wait_for(asyncio.shield(task), 5)
    elif stop == "none":
        assert await asyncio.wait_for(asyncio.shield(task), 5) is None
    else:
        expected = asyncio.CancelledError if stop == "cancel" else TimeoutError
        with pytest.raises(expected):
            await asyncio.wait_for(asyncio.shield(task), 5)


async def _control_plane_state(case):
    run = await case.service.execution_repository.get_run_record(run_id=_RUN_ID)
    attempt_id = f"{_RUN_ID}:attempt:0001"
    attempt = await case.service.execution_repository.get_attempt_record(attempt_id=attempt_id)
    checkpoint = await case.service.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{attempt_id}")
    acceptance = None if checkpoint is None else await case.service.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id)
    return run, attempt, checkpoint, acceptance


async def _assert_prefix(case, state, *, stage: str, stop: str, fault: bool) -> dict[str, object]:
    local = case.output / "checkpoint.json"
    snapshot_files = await asyncio.to_thread(
        lambda: sorted(case.output.glob("control_plane_checkpoint_snapshot_*.json")))
    run, attempt, checkpoint, acceptance = await _control_plane_state(case)
    if stage == "local" and (fault or stop != "none"):
        assert run is None and attempt is None and checkpoint is None and acceptance is None
    elif stage == "snapshot" and (fault or stop != "none"):
        assert run is not None and attempt is not None and checkpoint is None and acceptance is None
    else:
        assert all(value is not None for value in (run, attempt, checkpoint, acceptance))
    assert await asyncio.to_thread(local.is_dir if stage == "local" and fault else local.is_file)
    if stage == "snapshot" and fault:
        assert state.target is not None and await asyncio.to_thread(state.target.is_dir)
    elif stage == "snapshot":
        assert len(snapshot_files) == 1 and await asyncio.to_thread(snapshot_files[0].is_file)
    return {"run": run is not None, "checkpoint": checkpoint is not None,
            "local": await asyncio.to_thread(local.exists), "snapshots": len(snapshot_files)}


@pytest.mark.parametrize("stage", ["local", "snapshot"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("fault", [False, True], ids=["write", "late-directory-fault"])
async def test_checkpoint_publication_retains_native_prefix(
    tmp_path, monkeypatch, record_property, stage, stop, fault,
) -> None:
    """Layer: integration. Local and snapshot writes retain their real prefix."""
    case, state = _case(tmp_path), _hold_write(monkeypatch, stage, fault)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await write_checkpoint_fixture(
                executor=case.executor, turn=case.turn, context=case.context, prompt_hash="prompt-a")

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.worker != threading.get_ident() and len(state.calls) == 1
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        await _interrupt(stop, task, deadline)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        await _observe(task, stop=stop, fault=fault)
        assert state.finished.is_set()
        prefix = await _assert_prefix(case, state, stage=stage, stop=stop, fault=fault)
        record_property("checkpoint_publication_observation", json.dumps({
            "stage": stage, "stop": stop, "fault": state.fault, **prefix,
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, primary_error)
