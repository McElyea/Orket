from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.deployment_planner import DeploymentPlanner


@pytest.mark.asyncio
async def test_deployment_planner_creates_default_artifacts(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    planner = DeploymentPlanner(workspace_root=tmp_path, file_tools=fs, organization=None)

    result = await planner.ensure()

    assert isinstance(result["created_files"], list)
    assert (tmp_path / "agent_output" / "deployment" / "Dockerfile").is_file()
    assert (tmp_path / "agent_output" / "deployment" / "docker-compose.yml").is_file()
    assert (tmp_path / "agent_output" / "deployment" / "run_local.sh").is_file()


@pytest.mark.asyncio
async def test_deployment_planner_is_deterministic_on_rerun(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    planner = DeploymentPlanner(workspace_root=tmp_path, file_tools=fs, organization=None)

    first = await planner.ensure()
    second = await planner.ensure()

    assert len(second["created_files"]) == 0
    assert sorted(first["required_files"]) == sorted(second["required_files"])

