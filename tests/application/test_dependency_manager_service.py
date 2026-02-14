from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.dependency_manager import DependencyManager, DependencyValidationError


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


@pytest.mark.asyncio
async def test_dependency_manager_python_profile_policy_driven_sets(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "dependency_manager_stack_profile": "python",
                "dependency_manager_python_dependencies": [
                    "fastapi==0.115.0",
                    "pydantic==2.9.0",
                ],
                "dependency_manager_python_dev_dependencies": [
                    "pytest==8.3.0",
                ],
            }
        },
    )()
    manager = DependencyManager(workspace_root=tmp_path, file_tools=fs, organization=org)

    result = await manager.ensure()

    assert "agent_output/dependencies/pyproject.toml" in result["required_files"]
    assert "agent_output/dependencies/requirements.txt" in result["required_files"]
    assert "agent_output/dependencies/requirements-dev.txt" in result["required_files"]
    assert "agent_output/dependencies/package.json" not in result["required_files"]

    pyproject = (tmp_path / "agent_output" / "dependencies" / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (tmp_path / "agent_output" / "dependencies" / "requirements.txt").read_text(encoding="utf-8")
    requirements_dev = (tmp_path / "agent_output" / "dependencies" / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "fastapi==0.115.0" in pyproject
    assert "pytest==8.3.0" in pyproject
    assert "fastapi==0.115.0" in requirements
    assert "pytest==8.3.0" in requirements_dev


@pytest.mark.asyncio
async def test_dependency_manager_rejects_unpinned_python_dependencies(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "dependency_manager_stack_profile": "python",
                "dependency_manager_python_dependencies": ["fastapi>=0.115.0"],
            }
        },
    )()
    manager = DependencyManager(workspace_root=tmp_path, file_tools=fs, organization=org)

    with pytest.raises(DependencyValidationError, match="not pinned"):
        await manager.ensure()


@pytest.mark.asyncio
async def test_dependency_manager_node_profile_policy_driven_sets(tmp_path: Path):
    fs = AsyncFileTools(tmp_path)
    org = type(
        "Org",
        (),
        {
            "process_rules": {
                "dependency_manager_stack_profile": "node",
                "dependency_manager_node_dependencies": {
                    "react": "18.3.1",
                    "vite": "5.4.2",
                },
                "dependency_manager_node_dev_dependencies": {
                    "eslint": "9.10.0",
                },
            }
        },
    )()
    manager = DependencyManager(workspace_root=tmp_path, file_tools=fs, organization=org)

    result = await manager.ensure()

    assert "agent_output/dependencies/package.json" in result["required_files"]
    assert "agent_output/dependencies/pyproject.toml" not in result["required_files"]
    package_json = json.loads((tmp_path / "agent_output" / "dependencies" / "package.json").read_text(encoding="utf-8"))
    assert package_json["dependencies"]["react"] == "18.3.1"
    assert package_json["devDependencies"]["eslint"] == "9.10.0"
