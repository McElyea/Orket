"""Integration: native file operations retain admitted paths, references and content."""
import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def hold_path_method(monkeypatch, method, target):
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    original = getattr(Path, method)

    def held(path, *args, **kwargs):
        if path != target or state.entered.is_set():
            return original(path, *args, **kwargs)
        state.entered.set()
        try:
            assert state.release.wait(5), "Native file input fixture was not released"
            return original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, method, held)
    return state


@pytest.mark.parametrize("layer", ["adapter", "family"])
async def test_write_retains_content_and_roots_after_native_admission(tmp_path, monkeypatch, layer):
    original, changed = tmp_path / "original", tmp_path / "changed"
    await asyncio.to_thread(original.mkdir)
    await asyncio.to_thread(changed.mkdir)
    monkeypatch.chdir(original)
    tools = AsyncFileTools(Path("workspace")) if layer == "adapter" else FileSystemTools(Path("workspace"), [])
    file_tools = tools if layer == "adapter" else tools.async_fs
    content = {"values": ["admitted"]}
    state = hold_path_method(monkeypatch, "mkdir", original / "workspace")
    args = ["result.json", content] if layer == "adapter" else [{"path": "result.json", "content": content}]
    task = asyncio.create_task(tools.write_file(*args))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert not state.finished.is_set()
        content["values"].append("changed")
        file_tools.workspace_root = changed
        if layer == "family":
            args[0].update(path="changed.json", content={"values": ["replacement"]})
        monkeypatch.chdir(changed)
        state.release.set()
        result = await asyncio.wait_for(task, 5)
        actual_path = result if layer == "adapter" else result["path"]
        assert actual_path == str(original / "workspace/result.json")
        if layer == "family":
            assert result["ok"] is True
        value = json.loads(await asyncio.to_thread((original / "workspace/result.json").read_text, encoding="utf-8"))
        assert value == {"values": ["admitted"]}
        assert not await asyncio.to_thread((changed / "changed.json").exists)
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


@pytest.mark.parametrize("layer", ["adapter", "family"])
async def test_read_retains_reference_permission_after_native_admission(tmp_path, monkeypatch, layer):
    workspace, reference, changed = (tmp_path / name for name in ("workspace", "reference", "changed"))
    for path in (workspace, reference, changed):
        await asyncio.to_thread(path.mkdir)
    target = reference / "allowed.txt"
    await asyncio.to_thread(target.write_text, "admitted", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    references = [Path("reference")]
    tools = AsyncFileTools(Path("workspace"), references) if layer == "adapter" else FileSystemTools(Path("workspace"), references)
    file_tools = tools if layer == "adapter" else tools.async_fs
    state = hold_path_method(monkeypatch, "resolve", target)
    args = [str(target)] if layer == "adapter" else [{"path": str(target)}]
    task = asyncio.create_task(tools.read_file(*args))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        assert not state.finished.is_set()
        references[:] = [changed]
        file_tools.workspace_root = changed
        monkeypatch.chdir(changed)
        state.release.set()
        result = await asyncio.wait_for(task, 5)
        assert (result if layer == "adapter" else result["content"]) == "admitted"
    finally:
        state.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(state.finished.wait, 5)


@pytest.mark.parametrize("layer", ["adapter", "family"])
async def test_write_serialization_failure_precedes_native_effects(tmp_path, layer):
    workspace = tmp_path / "uncreated"
    content = {"invalid": object()}
    if layer == "adapter":
        with pytest.raises(TypeError):
            await AsyncFileTools(workspace).write_file("nested/result.json", content)
    else:
        result = await FileSystemTools(workspace, []).write_file({"path": "nested/result.json", "content": content})
        assert result["ok"] is False
    assert not await asyncio.to_thread(workspace.exists)
