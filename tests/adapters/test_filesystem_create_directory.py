from __future__ import annotations

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools


@pytest.mark.asyncio
async def test_async_file_tools_create_directory_stays_inside_workspace(tmp_path) -> None:
    """Layer: integration. Verifies create_directory uses the real workspace path boundary."""
    tools = AsyncFileTools(tmp_path)

    created = await tools.create_directory("agent_output/new-dir")

    assert (tmp_path / "agent_output" / "new-dir").is_dir()
    assert created.endswith("new-dir")


@pytest.mark.asyncio
async def test_filesystem_tool_create_directory_rejects_path_escape(tmp_path) -> None:
    """Layer: unit. Verifies create_directory shares file-tool path containment behavior."""
    tools = FileSystemTools(tmp_path, [])

    result = await tools.create_directory({"path": "../escape"})

    assert result["ok"] is False
    assert "outside allowed boundaries" in result["error"]
