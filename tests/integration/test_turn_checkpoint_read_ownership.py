"""Layer: integration. Checkpoint replay reads retain native settlement."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_executor_control_plane_evidence import load_checkpoint_snapshot_payload
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_REF = "turn-tool-checkpoint-snapshot:run-a:abc123"


def _destination(tmp_path: Path) -> TurnArtifactDestination:
    writer = TurnArtifactWriter(tmp_path)
    return TurnArtifactDestination(
        writer=writer, workspace=tmp_path, session_id="read-session", issue_id="READ-1",
        role_name="reviewer", role_id="REVIEWER", turn_index=4,
    )


def _snapshot_path(destination: TurnArtifactDestination) -> Path:
    return destination.file_path("control_plane_checkpoint_snapshot_abc123.json")


async def _seed(path: Path, content: str) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")


def _hold_read(monkeypatch, target: Path, fault: bool):
    original = Path.read_text
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            worker=None, fault="", calls=0)

    def held(path, *args, **kwargs):
        if path != target:
            return original(path, *args, **kwargs)
        state.calls += 1
        state.worker = threading.get_ident()
        state.entered.set()
        try:
            assert state.release.wait(5), "Native checkpoint read was not released"
            if fault:
                path.unlink()
                path.mkdir()
            return original(path, *args, **kwargs)
        except OSError as error:
            state.fault = type(error).__name__
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "read_text", held)
    return state


async def _interrupt(stop: str, task, deadline) -> None:
    if stop == "cancel":
        task.cancel()
    elif stop == "repeated":
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
    elif stop == "timeout":
        deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
    if stop != "none":
        await asyncio.sleep(0.03)


async def _settle(task, state, target: Path, primary_error: BaseException | None) -> None:
    state.release.set()
    if not task.done():
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert await asyncio.to_thread(state.finished.wait, 5)
    except BaseException as error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Checkpoint read cleanup also failed: {error!r}")
    if await asyncio.to_thread(target.is_dir):
        await asyncio.to_thread(target.rmdir)


async def _observe(task, *, stop: str, fault: bool):
    if stop == "none" and fault:
        with pytest.raises(TurnToolControlPlaneError, match="missing immutable checkpoint snapshot"):
            await asyncio.wait_for(asyncio.shield(task), 5)
        return None
    if stop == "none":
        return await asyncio.wait_for(asyncio.shield(task), 5)
    expected = TimeoutError if stop == "timeout" else asyncio.CancelledError
    with pytest.raises(expected):
        await asyncio.wait_for(asyncio.shield(task), 5)
    return None


@pytest.mark.parametrize("stop", ["none", "cancel", "repeated", "timeout"])
@pytest.mark.parametrize("fault", [False, True], ids=["read", "converted-directory-error"])
async def test_checkpoint_read_retains_native_settlement(
    tmp_path, monkeypatch, record_property, stop, fault,
) -> None:
    """Layer: integration. Converted read faults do not suppress interruption."""
    destination = _destination(tmp_path)
    target = _snapshot_path(destination)
    payload = {"run_id": "read-session", "issue_id": "READ-1", "role": "reviewer",
               "turn_index": 4, "namespace_scope": "issue:READ-1", "tool_calls": []}
    await _seed(target, json.dumps(payload))
    state = _hold_read(monkeypatch, target, fault)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await load_checkpoint_snapshot_payload(destination=destination, state_snapshot_ref=_REF)

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert state.worker != threading.get_ident() and state.calls == 1
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        await _interrupt(stop, task, deadline)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        observed = await _observe(task, stop=stop, fault=fault)
        assert state.finished.is_set()
        if stop == "none" and not fault:
            assert observed == payload
        if fault:
            assert state.fault in {"IsADirectoryError", "PermissionError", "OSError"}
        record_property("checkpoint_read_observation", json.dumps({
            "stop": stop, "native_error": state.fault, "target_is_directory":
            await asyncio.to_thread(target.is_dir),
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, target, primary_error)


@pytest.mark.parametrize("kind", ["missing", "invalid-json", "missing-tool-calls"])
async def test_checkpoint_read_preserves_missing_and_malformed_classification(tmp_path, kind) -> None:
    """Layer: integration. Existing absence and malformed classes stay distinct."""
    destination = _destination(tmp_path)
    target = _snapshot_path(destination)
    if kind == "invalid-json":
        await _seed(target, "{not-json")
    elif kind == "missing-tool-calls":
        await _seed(target, json.dumps({"run_id": "read-session"}))
    expected = "malformed for replay" if kind == "missing-tool-calls" else "missing immutable checkpoint snapshot"
    with pytest.raises(TurnToolControlPlaneError, match=expected):
        await load_checkpoint_snapshot_payload(destination=destination, state_snapshot_ref=_REF)
