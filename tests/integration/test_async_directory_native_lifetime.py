"""Integration: actual native mkdir/list work stays owned under interruption."""
import asyncio
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools
from tests.integration.test_async_file_native_lifetime import observe_native_operation

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_directory_call(monkeypatch, operation, target, state, failure):
    owner, name = (Path, "mkdir") if operation == "create_directory" else (os, "listdir")
    original = getattr(owner, name)

    def held(path, *args, **kwargs):
        if Path(path) != target or state.entered.is_set():
            return original(path, *args, **kwargs)
        state.entered.set()
        try:
            assert state.release.wait(5), "Native directory operation was not released"
            if failure:
                return list((target.parent / "absent-native-input").iterdir())
            return original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(owner, name, held)


@pytest.mark.parametrize("layer", ["adapter", "family"])
@pytest.mark.parametrize("operation", ["create_directory", "list_directory"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "failure"])
async def test_native_directory_operation_remains_owned(tmp_path, monkeypatch, record_property, layer, operation, stop):
    target = tmp_path / "target"
    if operation == "list_directory":
        await asyncio.to_thread(target.mkdir)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[])
    hold_directory_call(monkeypatch, operation, target, state, stop == "failure")
    adapter = AsyncFileTools(tmp_path) if layer == "adapter" else FileSystemTools(tmp_path, [])
    args = [target.name] if layer == "adapter" else [{"path": target.name}]
    await observe_native_operation(adapter, operation, args, tmp_path, state, stop, layer, record_property)
    if operation == "create_directory":
        assert await asyncio.to_thread(target.exists) is (stop != "failure")
