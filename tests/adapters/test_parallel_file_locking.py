import asyncio
import os

import pytest

from orket.adapters.tools.families import FileSystemTools

pytestmark = pytest.mark.integration


async def _parallel_writes(fs, paths):
    active_writes = 0
    max_active_writes = 0
    original_write = fs.async_fs.write_file

    async def instrumented_write(path_str, content):
        nonlocal active_writes, max_active_writes
        active_writes += 1
        max_active_writes = max(max_active_writes, active_writes)
        await asyncio.sleep(0.01)
        try:
            return await original_write(path_str, content)
        finally:
            active_writes -= 1

    fs.async_fs.write_file = instrumented_write

    tasks = [
        fs.write_file({"path": path, "content": f"payload-{i}"})
        for i, path in enumerate(paths)
    ]
    results = await asyncio.gather(*tasks)
    return results, max_active_writes


def _native_alias(path):
    if os.name == "nt":
        return type(path)("\\\\?\\" + str(path))
    return path.parent / "unused" / ".." / path.name


@pytest.mark.asyncio
async def test_write_file_uses_path_lock_for_parallel_writes(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fs = FileSystemTools(workspace, [])
    results, max_active_writes = await _parallel_writes(fs, ["shared/output.txt"] * 20)

    assert all(r["ok"] for r in results), results
    assert max_active_writes == 1

    final_content = (workspace / "shared" / "output.txt").read_text(encoding="utf-8")
    assert final_content.startswith("payload-")


@pytest.mark.asyncio
@pytest.mark.parametrize("alias_root", [False, True])
async def test_native_path_aliases_share_containment_and_write_lock(tmp_path, alias_root):
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir)
    fs = FileSystemTools(_native_alias(workspace) if alias_root else workspace, [])
    output = workspace / "shared" / "output.txt"
    aliases = ["shared/output.txt", str(output), str(_native_alias(output))]
    results, maximum = await _parallel_writes(fs, [aliases[index % 3] for index in range(20)])
    assert all(result["ok"] for result in results), results
    assert maximum == 1
    assert (await asyncio.to_thread(output.read_text, encoding="utf-8")).startswith("payload-")


@pytest.mark.asyncio
@pytest.mark.parametrize("alias_root", [False, True])
async def test_native_path_aliases_preserve_reference_and_outside_refusals(tmp_path, alias_root):
    workspace, reference = tmp_path / "workspace", tmp_path / "reference"
    await asyncio.to_thread(workspace.mkdir)
    await asyncio.to_thread(reference.mkdir)
    reference_file = reference / "retained.txt"
    await asyncio.to_thread(reference_file.write_text, "retained", encoding="utf-8")
    fs = FileSystemTools(_native_alias(workspace) if alias_root else workspace, [reference])
    read = await fs.read_file({"path": str(_native_alias(reference_file))})
    assert read == {"ok": True, "content": "retained"}
    denied = await fs.write_file({"path": str(_native_alias(reference_file)), "content": "changed"})
    assert not denied["ok"] and "Write access denied" in denied["error"]
    outside = tmp_path / "workspace_sibling" / "denied.txt"
    denied = await fs.write_file({"path": str(_native_alias(outside)), "content": "denied"})
    assert not denied["ok"] and "outside allowed boundaries" in denied["error"]
    assert not await asyncio.to_thread(outside.exists)
    assert await asyncio.to_thread(reference_file.read_text, encoding="utf-8") == "retained"
    created = await fs.create_directory({"path": str(_native_alias(workspace / "created"))})
    assert created["ok"], created
    assert await asyncio.to_thread((workspace / "created").is_dir)
