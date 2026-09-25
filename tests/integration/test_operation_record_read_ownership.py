"""Layer: integration. Operation record reads retain their admitted native worker."""
from __future__ import annotations

import asyncio
import json
import threading
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import (
    OperationRecordValidationError,
    TurnArtifactWriter,
)
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_OPERATION_ID = "operation-read-a"
_ARGS = {"path": "agent_output/a.txt", "content": "payload"}
_RESULT = {"ok": True, "touched_paths": ["agent_output/a.txt"]}


def _destination(tmp_path: Path) -> TurnArtifactDestination:
    writer = TurnArtifactWriter(tmp_path)
    return TurnArtifactDestination(
        writer=writer,
        workspace=tmp_path,
        session_id="operation-read-session",
        issue_id="OPERATION-READ-1",
        role_name="reviewer",
        role_id="REVIEWER",
        turn_index=2,
    )


async def _target(destination: TurnArtifactDestination) -> Path:
    return await run_owned_thread(
        partial(
            destination.writer.operation_result_path,
            destination=destination,
            operation_id=_OPERATION_ID,
        ),
        label="fixture-operation-result-path",
    )


async def _seed_valid(destination: TurnArtifactDestination) -> bytes:
    await run_owned_thread(
        partial(
            destination.writer.persist_operation_result,
            destination=destination,
            operation_id=_OPERATION_ID,
            tool_name="write_file",
            tool_args=_ARGS,
            result=_RESULT,
        ),
        label="fixture-operation-result-seed",
    )
    return await asyncio.to_thread((await _target(destination)).read_bytes)


@pytest.mark.parametrize("kind", ["missing", "invalid-json", "non-object", "valid"])
async def test_strict_operation_reader_distinguishes_missing_from_present_invalid(tmp_path, kind) -> None:
    """Layer: integration. Only FileNotFound is a cache miss; present-invalid fails closed."""
    destination = _destination(tmp_path)
    target = await _target(destination)
    before = None
    if kind == "valid":
        before = await _seed_valid(destination)
    elif kind != "missing":
        content = "{invalid-json" if kind == "invalid-json" else json.dumps(["not-an-object"])
        await asyncio.to_thread(target.write_text, content, encoding="utf-8")
        before = await asyncio.to_thread(target.read_bytes)

    operation = partial(
        destination.writer.load_operation_result,
        destination=destination,
        operation_id=_OPERATION_ID,
    )
    if kind == "missing":
        assert await run_owned_thread(operation, label="turn-operation-cache-read") is None
        assert not await asyncio.to_thread(target.exists)
    elif kind == "valid":
        observed = await run_owned_thread(operation, label="turn-operation-cache-read")
        assert observed["operation_id"] == _OPERATION_ID
    else:
        with pytest.raises(OperationRecordValidationError) as raised:
            await run_owned_thread(operation, label="turn-operation-cache-read")
        assert raised.value.reason == "malformed"
        assert "E_OPERATION_ARTIFACT_INVALID:malformed" in str(raised.value)
    if before is not None:
        assert await asyncio.to_thread(target.read_bytes) == before


def _hold_read(monkeypatch, target: Path, *, fault: bool):
    original = Path.read_text
    state = SimpleNamespace(
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        worker=None,
        expired=False,
        native_error="",
        calls=0,
        deadline=None,
    )

    def held(path, *args, **kwargs):
        if path != target or state.entered.is_set():
            return original(path, *args, **kwargs)
        state.calls += 1
        state.worker = threading.get_ident()
        state.entered.set()
        try:
            state.expired = not state.release.wait(0.8)
            if fault:
                path.unlink()
                path.mkdir()
            return original(path, *args, **kwargs)
        except OSError as error:
            state.native_error = type(error).__name__
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "read_text", held)
    return state


async def _interrupt(task, state, stop: str) -> None:
    if stop == "timeout":
        state.deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
    else:
        task.cancel()
        if stop == "repeated-cancel":
            await asyncio.sleep(0)
            task.cancel()
    await asyncio.sleep(0.03)


async def _observe(task, *, stop: str, fault: bool) -> None:
    if fault:
        with pytest.raises(OperationRecordValidationError) as raised:
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert raised.value.reason == "malformed"
        assert "present but unreadable" in str(raised.value)
        return
    expected = TimeoutError if stop == "timeout" else asyncio.CancelledError
    with pytest.raises(expected):
        await asyncio.wait_for(asyncio.shield(task), 5)


async def _settle(task, state, target: Path, primary_error: BaseException | None) -> None:
    state.release.set()
    if not task.done():
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert await asyncio.to_thread(state.finished.wait, 5)
        if await asyncio.to_thread(target.is_dir):
            await asyncio.to_thread(target.rmdir)
    except BaseException as cleanup_error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Operation read cleanup also failed: {cleanup_error!r}")


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "timeout"])
@pytest.mark.parametrize("fault", [False, True], ids=["settled-read", "late-oserror"])
async def test_interrupted_operation_read_drains_native_worker(
    tmp_path,
    monkeypatch,
    record_property,
    stop,
    fault,
) -> None:
    """Layer: integration. Cancellation cannot escape or admit a post-read stage."""
    destination = _destination(tmp_path)
    target = await _target(destination)
    before = await _seed_valid(destination)
    state = _hold_read(monkeypatch, target, fault=fault)
    stages = []

    async def operation():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            observed = await run_owned_thread(
                partial(
                    destination.writer.load_operation_result,
                    destination=destination,
                    operation_id=_OPERATION_ID,
                ),
                label="turn-operation-cache-read",
            )
            stages.append("after-read")
            return observed

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.worker != threading.get_ident() and state.calls == 1
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not state.expired
        await _interrupt(task, state, stop)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        await _observe(task, stop=stop, fault=fault)
        assert task.done() and state.finished.is_set() and stages == []
        if fault:
            assert state.native_error in {"IsADirectoryError", "PermissionError", "OSError"}
            assert await asyncio.to_thread(target.is_dir)
        else:
            assert await asyncio.to_thread(target.read_bytes) == before
        record_property(
            "operation_read_observation",
            json.dumps(
                {"stop": stop, "fault": state.native_error, "native_finished": state.finished.is_set()},
                sort_keys=True,
            ),
        )
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, target, primary_error)
