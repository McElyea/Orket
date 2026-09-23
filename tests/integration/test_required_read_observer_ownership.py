"""Layer: integration. Shared required-read observation keeps policy and native ownership."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from orket.application.workflows import turn_read_context
from orket.application.workflows.turn_read_context import (
    RequiredReadObservation,
    observe_available_required_read_paths,
    observe_legacy_required_read_paths,
    observe_required_read_paths,
    observe_workspace_constraint_violation,
)
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_direct_metadata_lifetime import held_metadata

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _write(path: Path, content: str = "observed\n") -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")


def _observation(kind: str, workspace: Path, token: str):
    if kind == "governed":
        return observe_required_read_paths(
            context={"required_read_paths": [token]}, workspace=workspace,
        )
    if kind == "legacy":
        return observe_legacy_required_read_paths(
            context={"required_read_paths": [token]}, workspace=workspace,
        )
    if kind == "available":
        return observe_available_required_read_paths(required_paths=[token], workspace=workspace)
    return observe_workspace_constraint_violation(
        tool_name="read_file", args={"path": token}, workspace=workspace,
    )


async def test_observers_preserve_their_distinct_path_classifications(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    await _write(workspace / "present.txt")
    await asyncio.to_thread((workspace / "directory").mkdir, parents=True)
    await _write(tmp_path / "outside.txt")
    declared = ["present.txt", "directory", "missing.txt", "../outside.txt"]

    legacy = await observe_legacy_required_read_paths(
        context={"required_read_paths": declared}, workspace=workspace,
    )
    available = await observe_available_required_read_paths(
        required_paths=declared, workspace=workspace,
    )

    assert legacy == RequiredReadObservation(
        existing=("present.txt", "../outside.txt"),
        missing=("directory", "missing.txt"),
    )
    assert available == ("present.txt", "directory", "../outside.txt")
    with pytest.raises(ValueError, match=r"E_WORKSPACE_CONSTRAINT:read_file:path_traversal"):
        await observe_required_read_paths(
            context={"required_read_paths": ["../outside.txt"]}, workspace=workspace,
        )
    assert await observe_workspace_constraint_violation(
        tool_name="read_file", args={"path": "../outside.txt"}, workspace=workspace,
    ) == "read_file:path_traversal"


async def test_empty_and_non_path_observations_admit_no_native_worker(tmp_path, monkeypatch) -> None:
    async def forbidden_worker(*_args, **_kwargs):
        raise AssertionError("no native worker should be admitted")

    monkeypatch.setattr(turn_read_context, "run_owned_thread", forbidden_worker)
    assert await observe_required_read_paths(context={}, workspace=tmp_path) == RequiredReadObservation((), ())
    assert await observe_legacy_required_read_paths(context={}, workspace=tmp_path) == RequiredReadObservation((), ())
    assert await observe_available_required_read_paths(required_paths=[], workspace=tmp_path) == ()
    assert await observe_workspace_constraint_violation(
        tool_name="add_issue_comment", args={"path": "../ignored"}, workspace=tmp_path,
    ) is None
    assert RequiredReadObservation(["a"], ["b"]) == RequiredReadObservation(("a",), ("b",))


@pytest.mark.parametrize("kind,method", [
    ("governed", "resolve"), ("governed", "exists"), ("governed", "is_file"),
    ("legacy", "resolve"), ("legacy", "exists"), ("legacy", "is_file"),
    ("available", "resolve"), ("available", "exists"), ("submitted", "resolve"),
])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "native-failure"])
async def test_observer_native_work_settles_and_late_failure_stays_visible(
    tmp_path, monkeypatch, record_property, kind, method, stop,
) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "held.txt"
    await _write(target)
    state = held_metadata(monkeypatch, target, method, stop == "native-failure")
    deadline = asyncio.timeout(None)

    async def operation():
        async with deadline:
            return await _observation(kind, workspace, "held.txt")

    timer = threading.Timer(0.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        if stop == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        expected = OSError if stop == "native-failure" else TimeoutError if stop == "timeout" else asyncio.CancelledError
        with pytest.raises(expected, match="controlled native" if stop == "native-failure" else None):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert not timer.is_alive() and state.finished.is_set()
