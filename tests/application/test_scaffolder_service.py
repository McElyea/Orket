from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.scaffolder import Scaffolder, ScaffoldValidationError


@pytest.mark.asyncio
async def test_scaffolder_creates_default_structure(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    scaffolder = Scaffolder(workspace_root=tmp_path, file_tools=fs, organization=None)

    result = await scaffolder.ensure()

    assert isinstance(result["created_directories"], list)
    assert isinstance(result["created_files"], list)
    assert (tmp_path / "agent_output" / "src").is_dir()
    assert (tmp_path / "agent_output" / "tests").is_dir()
    assert (tmp_path / "agent_output" / "README.md").is_file()
    assert (tmp_path / "agent_output" / ".env.example").is_file()


@pytest.mark.asyncio
async def test_scaffolder_is_deterministic_across_reruns(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    scaffolder = Scaffolder(workspace_root=tmp_path, file_tools=fs, organization=None)

    first = await scaffolder.ensure()
    second = await scaffolder.ensure()

    assert len(second["created_directories"]) == 0
    assert len(second["created_files"]) == 0
    assert sorted(first["required_directories"]) == sorted(second["required_directories"])
    assert sorted(first["required_files"]) == sorted(second["required_files"])


@pytest.mark.asyncio
async def test_scaffolder_raises_on_forbidden_extension(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = SimpleNamespace(
        process_rules={
            "scaffolder_forbidden_extensions": [".exe"],
        }
    )
    scaffolder = Scaffolder(workspace_root=tmp_path, file_tools=fs, organization=org)

    (tmp_path / "agent_output").mkdir(parents=True, exist_ok=True)
    (tmp_path / "agent_output" / "danger.exe").write_text("x", encoding="utf-8")

    with pytest.raises(ScaffoldValidationError, match="Forbidden file types detected"):
        await scaffolder.ensure()


@pytest.mark.asyncio
async def test_scaffolder_api_vue_profile_creates_frontend_structure(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = SimpleNamespace(process_rules={"project_surface_profile": "api_vue"})
    scaffolder = Scaffolder(
        workspace_root=tmp_path,
        file_tools=fs,
        organization=org,
        project_surface_profile="api_vue",
    )

    await scaffolder.ensure()

    assert (tmp_path / "agent_output" / "frontend" / "index.html").is_file()
    assert (tmp_path / "agent_output" / "frontend" / "src" / "main.js").is_file()


@pytest.mark.asyncio
async def test_scaffolder_backend_only_profile_skips_frontend_structure(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = SimpleNamespace(process_rules={"project_surface_profile": "backend_only"})
    scaffolder = Scaffolder(
        workspace_root=tmp_path,
        file_tools=fs,
        organization=org,
        project_surface_profile="backend_only",
    )

    await scaffolder.ensure()

    assert not (tmp_path / "agent_output" / "frontend").exists()
