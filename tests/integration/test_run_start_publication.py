"""Actual bootstrap files and native rename holds; no inference about the original holder."""
from __future__ import annotations

import asyncio
import ctypes
import os
import threading
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path

import pytest

import orket.runtime.evidence.run_start_artifacts as artifacts

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
NOW = datetime(2026, 9, 19, 16, tzinfo=UTC)


def _hold(path):
    """Called in a worker. Windows denies delete sharing; POSIX permits open-file rename."""
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        return lambda: os.close(descriptor)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 3, None, 3,
                                0x02000000 if path.is_dir() else 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    def close():
        if not kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())

    return close


def _files(root):
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def _held_capture(tmp_path, monkeypatch, kind):
    entered, state = threading.Event(), {}
    original = artifacts._resolve_workspace_state_snapshot

    def capture_snapshot(**kwargs):
        result = original(**kwargs)
        stage = kwargs["path"].parent
        state.update(stage=stage, expected=_files(stage), close=_hold(
            stage if kind == "directory" else stage / "run_identity.json"))
        entered.set()
        return result

    monkeypatch.setattr(artifacts, "_resolve_workspace_state_snapshot", capture_snapshot)
    request = asyncio.create_task(asyncio.to_thread(artifacts.capture_run_start_artifacts,
        workspace=tmp_path, run_id="held", workload="core_epic", now=NOW))
    return entered, state, request


@pytest.mark.parametrize("kind", ["directory", "member"])
async def test_run_start_publication_recovers_after_native_hold_release(tmp_path, monkeypatch, kind, caplog):
    """Layer: integration. The same completed tree publishes after a real native hold ends."""
    entered, state, request = _held_capture(tmp_path, monkeypatch, kind)
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        await asyncio.sleep(0.15)
        if os.name == "nt":
            assert not request.done(), "Publication must retain its bounded retry while held"
            assert not state["stage"].with_name("runtime_contracts").exists()
        await asyncio.to_thread(state.pop("close"))
        result = await asyncio.wait_for(asyncio.shield(request), 5)
        root = Path(result["run_identity_path"]).parent
        assert await asyncio.to_thread(_files, root) == state["expected"]
        assert not state["stage"].exists()
        if os.name == "nt":
            assert "E_RUN_START_ARTIFACTS_PUBLISH_RETRY" in caplog.text
            assert "RUN_START_ARTIFACTS_PUBLISHED_AFTER_RETRY" in caplog.text
    finally:
        if close := state.pop("close", None):
            await asyncio.to_thread(close)
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 5)


@pytest.mark.parametrize("kind", ["directory", "member"])
async def test_persistent_native_hold_retains_incomplete_stage_and_refuses_replay(tmp_path, monkeypatch, kind):
    """Layer: integration. Windows exhaustion preserves evidence; POSIX open handles allow rename."""
    entered, state, request = _held_capture(tmp_path, monkeypatch, kind)
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        result, = await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 5)
        if os.name == "nt":
            assert isinstance(result, RuntimeError) and "E_RUN_START_ARTIFACTS_PUBLISH_BLOCKED" in str(result)
            assert isinstance(result.__cause__, PermissionError) and result.__cause__.winerror in {5, 32}
            assert not state["stage"].with_name("runtime_contracts").exists()
            assert await asyncio.to_thread(_files, state["stage"]) == state["expected"]
            await asyncio.to_thread(state.pop("close"))
            with pytest.raises(ValueError, match="E_RUN_START_ARTIFACTS_INCOMPLETE"):
                await asyncio.to_thread(artifacts.capture_run_start_artifacts,
                    workspace=tmp_path, run_id="held", workload="core_epic", now=NOW)
        else:
            assert isinstance(result, dict)
            assert await asyncio.to_thread(_files, Path(result["run_identity_path"]).parent) == state["expected"]
    finally:
        if close := state.pop("close", None):
            await asyncio.to_thread(close)
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 5)


async def test_run_start_publication_refuses_an_existing_destination(tmp_path, monkeypatch):
    """Layer: integration. An independently created destination is retained with the staging evidence."""
    original = artifacts._resolve_workspace_state_snapshot
    state = {}

    def conflict(**kwargs):
        result = original(**kwargs)
        stage = kwargs["path"].parent
        target = stage.with_name("runtime_contracts")
        target.mkdir()
        state.update(stage=stage, target=target, identity=target.stat().st_ino, expected=_files(stage))
        return result

    monkeypatch.setattr(artifacts, "_resolve_workspace_state_snapshot", conflict)
    with pytest.raises(ValueError, match="E_RUN_START_ARTIFACTS_PUBLISH_CONFLICT"):
        await asyncio.to_thread(artifacts.capture_run_start_artifacts,
            workspace=tmp_path, run_id="conflict", workload="core_epic", now=NOW)
    assert state["target"].stat().st_ino == state["identity"]
    assert await asyncio.to_thread(_files, state["stage"]) == state["expected"]
