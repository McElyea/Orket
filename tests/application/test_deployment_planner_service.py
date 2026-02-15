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


@pytest.mark.asyncio
async def test_deployment_planner_backend_profile_omits_compose(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = type("Org", (), {"process_rules": {"project_surface_profile": "backend_only"}})()
    planner = DeploymentPlanner(
        workspace_root=tmp_path,
        file_tools=fs,
        organization=org,
        project_surface_profile="backend_only",
    )
    result = await planner.ensure()

    assert "agent_output/deployment/docker-compose.yml" not in result["required_files"]
    assert (tmp_path / "agent_output" / "deployment" / "Dockerfile").is_file()


@pytest.mark.asyncio
async def test_deployment_planner_api_vue_profile_includes_frontend_service(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = type("Org", (), {"process_rules": {"project_surface_profile": "api_vue"}})()
    planner = DeploymentPlanner(
        workspace_root=tmp_path,
        file_tools=fs,
        organization=org,
        project_surface_profile="api_vue",
    )
    await planner.ensure()

    compose = (tmp_path / "agent_output" / "deployment" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "frontend:" in compose


@pytest.mark.asyncio
async def test_deployment_planner_microservices_pattern_writes_multi_service_artifacts(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    planner = DeploymentPlanner(
        workspace_root=tmp_path,
        file_tools=fs,
        organization=None,
        architecture_pattern="microservices",
    )
    result = await planner.ensure()

    assert "agent_output/deployment/Dockerfile.api" in result["required_files"]
    assert "agent_output/deployment/Dockerfile.worker" in result["required_files"]
    compose = (tmp_path / "agent_output" / "deployment" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "worker:" in compose
