from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.manager import ExtensionManager
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.interfaces.orket_bundle_cli import validate_external_extension


def _agent_manifest() -> dict[str, object]:
    return {
        "manifest_version": "v0",
        "extension_id": "test.agent",
        "extension_version": "0.1.0",
        "workloads": [
            {
                "workload_id": "governed-agent-loop",
                "entrypoint": "test_agent:run",
                "required_capabilities": ["agent.iteration.v1"],
                "workload_kind": "agent",
                "input_contract": "agent_iteration_request.v1",
                "output_contract": "agent_iteration_result.v1",
                "agent": {
                    "contract_version": "governed_agent_loop.v1",
                    "required_host_features": ["governed_agent_loop.v1", "agent_stdio_ipc.v1", "agent_model_use_receipt.v2"],
                    "model_profiles": [{"role": "planner", "profile_ref": "local.default"}],
                    "resource_requirements": {"max_model_calls_per_iteration": 2},
                },
            }
        ],
    }


def _write_agent_repo(path: Path) -> None:
    path.mkdir()
    (path / "extension.json").write_text(json.dumps(_agent_manifest()), encoding="utf-8")
    (path / "test_agent.py").write_text("def run(ctx, payload):\n    raise AssertionError('must not run')\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_host_validation_accepts_implemented_agent_features(tmp_path: Path) -> None:
    extension = tmp_path / "extension"
    extension.mkdir()
    (extension / "extension.json").write_text(json.dumps(_agent_manifest()), encoding="utf-8")
    (extension / "test_agent.py").write_text("def run(ctx, payload):\n    return None\n", encoding="utf-8")

    result = validate_external_extension(extension, strict=True)

    assert result["ok"] is True
    assert result["errors"] == []


def test_host_validation_refuses_unknown_agent_feature(tmp_path: Path) -> None:
    extension = tmp_path / "extension"
    extension.mkdir()
    manifest = _agent_manifest()
    workloads = manifest["workloads"]
    assert isinstance(workloads, list)
    workload = workloads[0]
    assert isinstance(workload, dict)
    agent = workload["agent"]
    assert isinstance(agent, dict)
    features = agent["required_host_features"]
    assert isinstance(features, list)
    features.append("agent.streaming.v2")
    (extension / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    (extension / "test_agent.py").write_text("def run(ctx, payload):\n    return None\n", encoding="utf-8")

    result = validate_external_extension(extension, strict=True)

    assert result["ok"] is False
    assert [item["code"] for item in result["errors"]] == ["E_AGENT_HOST_FEATURE_UNSUPPORTED"]


def test_install_publishes_agent_for_dedicated_catalog_resolution(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_agent_repo(repo)
    catalog_path = tmp_path / "catalog.json"
    manager = ExtensionManager(catalog_path=catalog_path, project_root=tmp_path)
    manager.install_root = tmp_path / "installed"
    manager.install_root.mkdir()

    installed = manager.install_from_repo(str(repo))
    launch = manager.resolve_governed_agent_workload("governed-agent-loop")

    assert catalog_path.exists()
    assert installed.extension_id == "test.agent"
    assert launch.extension_id == "test.agent"
    assert launch.entrypoint == "test_agent:run"
    assert launch.agent_declaration["contract_version"] == "governed_agent_loop.v1"


def test_catalog_reload_refuses_marker_only_legacy_row(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "forged.agent",
                        "extension_version": "0.1.0",
                        "contract_style": "sdk_v0",
                        "manifest_entries": [
                            {
                                "workload_id": "generic-name",
                                "workload_version": "0.1.0",
                                "entrypoint": "forged:run",
                                "required_capabilities": ["agent.iteration.v1"],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_SDK_AGENT_DECLARATION_INVALID"):
        ExtensionCatalog(catalog_path).list_extensions()


@pytest.mark.parametrize("capability", ["agent.iteration.v1", "read_file", "write_file"])
def test_child_configuration_cannot_materialize_agent_host_authority(
    tmp_path: Path,
    capability: str,
) -> None:
    with pytest.raises(ValueError, match="E_SDK_HOST_BOUND_CAPABILITY_CONFIG_FORBIDDEN"):
        WorkloadArtifacts.build_sdk_capability_registry(
            workspace=tmp_path,
            artifact_root=tmp_path / "artifacts",
            input_config={"capabilities": {capability: object()}},
        )
