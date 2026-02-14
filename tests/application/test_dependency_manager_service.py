from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.dependency_manager import DependencyManager


@pytest.mark.asyncio
async def test_dependency_manager_creates_default_manifests(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    manager = DependencyManager(workspace_root=tmp_path, file_tools=fs, organization=None)

    result = await manager.ensure()

    assert isinstance(result["created_files"], list)
    assert (tmp_path / "agent_output" / "dependencies" / "pyproject.toml").is_file()
    assert (tmp_path / "agent_output" / "dependencies" / "requirements.txt").is_file()
    assert (tmp_path / "agent_output" / "dependencies" / "package.json").is_file()


@pytest.mark.asyncio
async def test_dependency_manager_is_deterministic_on_rerun(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    manager = DependencyManager(workspace_root=tmp_path, file_tools=fs, organization=None)

    first = await manager.ensure()
    second = await manager.ensure()

    assert len(second["created_files"]) == 0
    assert sorted(first["required_files"]) == sorted(second["required_files"])

