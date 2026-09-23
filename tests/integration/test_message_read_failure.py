"""Layer: integration. Late physical read failures cannot become missing-input omission."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace

import aiofiles.threadpool
import pytest

from orket.application.workflows.turn_message_builder import MessageBuilder
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import prepare_message_fixture
from tests.integration.test_message_read_ownership import _context, _issue, _role, _write_bytes

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATH = "agent_output/requirements.txt"


def _hold_then_change_file(monkeypatch, target: Path, fault: str):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    original = aiofiles.threadpool.sync_open

    def changed_open(file, *args, **kwargs):
        if isinstance(file, int) or Path(file) != target:
            return original(file, *args, **kwargs)
        state.entered.set()
        try:
            assert state.release.wait(5), "Native open was not released"
            # This native fixture action models external replacement after the
            # preceding positive metadata observation; no source path is touched.
            if fault == "missing":
                target.unlink()
            elif fault == "directory":
                target.unlink()
                target.mkdir()
            else:
                target.write_bytes(b"\xff invalid UTF-8")
            stream = original(file, *args, **kwargs)
            state.streams.append(stream)
            return stream
        finally:
            state.finished.set()

    monkeypatch.setattr(aiofiles.threadpool, "sync_open", changed_open)
    return state


@pytest.mark.parametrize("fault", ["missing", "decode", "directory"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_late_preload_failure_survives_native_settlement(tmp_path: Path, monkeypatch, record_property, fault, stop):
    target = tmp_path / _READ_PATH
    before = b"Originally admitted regular file.\n"
    await _write_bytes(target, before)
    await _write_bytes(tmp_path / "retained-before.bin", await asyncio.to_thread(target.read_bytes))
    state = _hold_then_change_file(monkeypatch, target, fault)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await prepare_message_fixture(MessageBuilder(tmp_path), issue=_issue(), role=_role(), context=_context())

    timer = threading.Timer(0.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        elif stop == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
        if stop != "none":
            await asyncio.sleep(0.03)
            assert not task.done() and not state.finished.is_set()
        state.release.set()
        expected = FileNotFoundError if fault == "missing" else UnicodeDecodeError
        if fault == "directory":
            expected = (PermissionError, IsADirectoryError)
        with pytest.raises(expected) as raised:
            await asyncio.wait_for(asyncio.shield(task), 5)
        record_property("observed_read_error", type(raised.value).__name__)
        assert state.finished.is_set() and all(stream.closed for stream in state.streams)
        if fault == "missing":
            assert not await asyncio.to_thread(target.exists)
        elif fault == "directory":
            assert await asyncio.to_thread(target.is_dir)
        else:
            assert await asyncio.to_thread(target.read_bytes) == b"\xff invalid UTF-8"
        assert await asyncio.to_thread((tmp_path / "retained-before.bin").read_bytes) == before
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
        for stream in state.streams:
            await asyncio.to_thread(stream.close)
        assert not timer.is_alive()
