"""Layer: integration. Real memory publication lifetime and native failure controls."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_memory_trace_artifacts import (
    MemoryTraceInputs,
    publish_memory_trace,
    render_memory_trace_publication,
)
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _destination(root: Path) -> TurnArtifactDestination:
    writer = TurnArtifactWriter(root)
    return TurnArtifactDestination(
        writer=writer,
        workspace=root,
        session_id="memory-session",
        issue_id="memory-issue",
        role_name="reviewer",
        role_id="REVIEWER",
        turn_index=1,
    )


def _publication(destination: TurnArtifactDestination):
    inputs = MemoryTraceInputs(
        enabled=True,
        normalization_version="json-v1",
        tool_profile_version="profile-v1",
        event_normalization_version="json-v1",
        event_tool_profile_version="profile-v1",
        workflow_id="turn_executor",
        memory_snapshot_id="snapshot-a",
        visibility_mode="read_only",
        model_config_id="model-a",
        policy_set_id="policy-a",
        output_type="text",
    )
    publication = render_memory_trace_publication(
        destination=destination,
        inputs=inputs,
        event_sink=[{
            "role": "reviewer",
            "interceptor": "turn",
            "decision_type": "execute_turn",
            "tool_calls": [],
            "guardrails_triggered": [],
            "retrieval_event_ids": ["ret-a"],
        }],
        turn=None,
        guardrails_triggered=[],
        retrieval_events=[{"retrieval_event_id": "ret-a", "payload": {"value": "original"}}],
    )
    assert publication is not None
    return publication


def _paths(destination: TurnArtifactDestination) -> tuple[Path, Path]:
    return (
        destination.file_path("memory_trace.json"),
        destination.file_path("memory_retrieval_trace.json"),
    )


def _hold_write(monkeypatch, target: Path, *, fault: bool):
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        calls=[], threads=[], fault="",
    )
    original = Path.write_text

    def held(path, *args, **kwargs):
        state.calls.append(path)
        if path != target:
            return original(path, *args, **kwargs)
        state.threads.append(threading.get_ident())
        state.entered.set()
        try:
            assert state.release.wait(5), "Native memory write was not released"
            if fault:
                path.mkdir()
            try:
                return original(path, *args, **kwargs)
            except (PermissionError, IsADirectoryError) as error:
                state.fault = type(error).__name__
                raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "write_text", held)
    return state


async def _settle(task, state) -> None:
    state.release.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    if state.entered.is_set():
        assert await asyncio.to_thread(state.finished.wait, 5)


@pytest.mark.parametrize("stage", ["first", "second"])
async def test_memory_publication_preserves_real_native_failure_prefix(
    tmp_path, monkeypatch, record_property, stage,
):
    destination = _destination(tmp_path)
    publication = _publication(destination)
    memory, retrieval = _paths(destination)
    target = memory if stage == "first" else retrieval
    state = _hold_write(monkeypatch, target, fault=True)
    task = asyncio.create_task(
        publish_memory_trace(destination=destination, publication=publication)
    )
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.threads == [state.threads[0]]
        assert state.threads[0] != threading.get_ident()
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        state.release.set()
        with pytest.raises((PermissionError, IsADirectoryError)):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        assert await asyncio.to_thread(target.is_dir)
        memory_is_file, retrieval_exists = await asyncio.gather(
            asyncio.to_thread(memory.is_file), asyncio.to_thread(retrieval.exists),
        )
        if stage == "first":
            assert not retrieval_exists
        else:
            assert memory_is_file
        if stage == "second":
            assert await asyncio.to_thread(memory.read_text, encoding="utf-8") == publication.memory_trace
        record_property("memory_native_failure", json.dumps({
            "stage": stage,
            "fault": state.fault,
            "memory_is_file": memory_is_file,
            "retrieval_is_file": await asyncio.to_thread(retrieval.is_file),
            "calls": [str(path) for path in state.calls],
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state)
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Memory publication cleanup also failed: {error!r}")


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_memory_publication_retains_owned_batch_and_captured_destination(
    tmp_path, monkeypatch, record_property, stop,
):
    destination = _destination(tmp_path / "original")
    publication = _publication(destination)
    memory, retrieval = _paths(destination)
    state = _hold_write(monkeypatch, memory, fault=False)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            await publish_memory_trace(destination=destination, publication=publication)

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.threads == [state.threads[0]]
        assert state.threads[0] != threading.get_ident()
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        destination.writer.workspace = tmp_path / "changed"
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        elif stop == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + .01)
        if stop != "none":
            await asyncio.sleep(.03)
            assert not task.done()
        assert not state.finished.is_set()
        state.release.set()
        if stop == "none":
            await asyncio.wait_for(asyncio.shield(task), 5)
        else:
            expected = asyncio.CancelledError if stop == "cancel" else TimeoutError
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        memory_text, retrieval_text, changed_exists = await asyncio.gather(
            asyncio.to_thread(memory.read_text, encoding="utf-8"),
            asyncio.to_thread(retrieval.read_text, encoding="utf-8"),
            asyncio.to_thread((tmp_path / "changed" / "observability").exists),
        )
        assert memory_text == publication.memory_trace
        assert retrieval_text == publication.retrieval_trace
        assert not changed_exists
        record_property("memory_owned_batch", json.dumps({
            "stop": stop,
            "native_finished": state.finished.is_set(),
            "memory": json.loads(memory_text),
            "retrieval": json.loads(retrieval_text),
            "calls": [str(path) for path in state.calls],
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state)
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Memory publication cleanup also failed: {error!r}")
