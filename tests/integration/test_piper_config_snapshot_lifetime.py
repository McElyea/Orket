"""Real snapshot acquisition/cleanup remains owned through delayed filesystem work."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from orket.capabilities import piper_voice_assets


@pytest.mark.asyncio
# Layer: integration
async def test_cancelled_snapshot_acquisition_drains_write_and_removes_the_created_directory(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original_write = Path.write_bytes
    observed = []

    def delayed_write(path, data):
        if path.name == "model.onnx.json":
            observed.append(path)
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Test did not release snapshot creation")
        return original_write(path, data)

    async def use_snapshot():
        async with piper_voice_assets.piper_config_snapshot(tmp_path, b"{}"):
            pytest.fail("Cancelled acquisition admitted snapshot use")

    monkeypatch.setattr(Path, "write_bytes", delayed_write)
    task = asyncio.create_task(use_snapshot())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done() and await asyncio.to_thread(observed[0].parent.exists)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not await asyncio.to_thread(observed[0].parent.exists)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("fail", [False, True])
# Layer: integration
async def test_snapshot_cleanup_settles_before_cancellation_and_preserves_failure(tmp_path, monkeypatch, fail):
    entered, release = threading.Event(), threading.Event()
    original_remove = piper_voice_assets.shutil.rmtree
    observed = []

    def delayed_remove(path):
        observed.append(path)
        entered.set()
        if not release.wait(5):
            raise TimeoutError("Test did not release snapshot cleanup")
        if fail:
            raise OSError("controlled snapshot cleanup failure")
        original_remove(path)

    async def use_snapshot():
        async with piper_voice_assets.piper_config_snapshot(tmp_path, b"{}") as config:
            assert await asyncio.to_thread(config.read_bytes) == b"{}"

    monkeypatch.setattr(piper_voice_assets.shutil, "rmtree", delayed_remove)
    task = asyncio.create_task(use_snapshot())
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(OSError if fail else asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(observed[0].exists) is fail
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        for folder in observed:
            if await asyncio.to_thread(folder.exists):
                assert folder.resolve().is_relative_to(tmp_path.resolve())
                await asyncio.to_thread(original_remove, folder)
