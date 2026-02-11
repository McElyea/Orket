import asyncio

import pytest

from orket.tools import FileSystemTools


@pytest.mark.asyncio
async def test_write_file_uses_path_lock_for_parallel_writes(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fs = FileSystemTools(workspace, [])

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
        fs.write_file({"path": "shared/output.txt", "content": f"payload-{i}"})
        for i in range(20)
    ]
    results = await asyncio.gather(*tasks)

    assert all(r["ok"] for r in results)
    assert max_active_writes == 1

    final_content = (workspace / "shared" / "output.txt").read_text(encoding="utf-8")
    assert final_content.startswith("payload-")
