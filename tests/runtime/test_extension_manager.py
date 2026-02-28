from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orket.extensions.manager import ExtensionManager


def _init_test_extension_repo(repo_root):
    manifest = {
        "extension_id": "mystery.extension",
        "extension_version": "1.0.0",
        "extension_api_version": "1.0.0",
        "module": "mystery_extension",
        "register_callable": "register",
        "workloads": [{"workload_id": "mystery_v1", "workload_version": "1.0.0"}],
    }
    (repo_root / "orket_extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "mystery_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from orket.extensions import RunPlan, RunAction",
                "",
                "class MysteryWorkload:",
                "    workload_id = 'mystery_v1'",
                "    workload_version = '1.0.0'",
                "",
                "    def compile(self, input_config):",
                "        _ = dict(input_config or {})",
                "        return RunPlan(",
                "            workload_id='mystery_v1',",
                "            workload_version='1.0.0',",
                "            actions=(),",
                "            metadata={'policy': 'truth-or-silence'},",
                "        )",
                "",
                "    def validators(self):",
                "        return []",
                "",
                "    def summarize(self, run_artifacts):",
                "        return {'ok': True, 'artifacts': sorted(run_artifacts.keys())}",
                "",
                "    def required_materials(self):",
                "        return []",
                "",
                "def register(registry):",
                "    registry.register_workload(MysteryWorkload())",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_blocked_import_extension_repo(repo_root):
    manifest = {
        "extension_id": "blocked.extension",
        "extension_version": "1.0.0",
        "extension_api_version": "1.0.0",
        "module": "blocked_extension",
        "register_callable": "register",
        "workloads": [{"workload_id": "blocked_v1", "workload_version": "1.0.0"}],
    }
    (repo_root / "orket_extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "blocked_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from orket.orchestration.engine import OrchestrationEngine",
                "from orket.extensions import RunPlan",
                "",
                "class BlockedWorkload:",
                "    workload_id = 'blocked_v1'",
                "    workload_version = '1.0.0'",
                "    def compile(self, input_config):",
                "        _ = OrchestrationEngine",
                "        return RunPlan(workload_id='blocked_v1', workload_version='1.0.0', actions=())",
                "    def validators(self):",
                "        return []",
                "    def summarize(self, run_artifacts):",
                "        return {'ok': True}",
                "    def required_materials(self):",
                "        return []",
                "",
                "def register(registry):",
                "    registry.register_workload(BlockedWorkload())",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def test_list_extensions_from_catalog(tmp_path):
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "workloads": [
                            {"workload_id": "mystery_v1", "workload_version": "1.0.0"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = ExtensionManager(catalog_path=catalog)
    extensions = manager.list_extensions()

    assert len(extensions) == 1
    assert extensions[0].extension_id == "mystery.extension"
    assert extensions[0].workloads[0].workload_id == "mystery_v1"


def test_resolve_workload_returns_extension_and_workload(tmp_path):
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "workloads": [
                            {"workload_id": "mystery_v1", "workload_version": "1.0.0"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = ExtensionManager(catalog_path=catalog)
    resolved = manager.resolve_workload("mystery_v1")

    assert resolved is not None
    extension, workload = resolved
    assert extension.extension_id == "mystery.extension"
    assert workload.workload_id == "mystery_v1"


def test_install_from_repo_registers_extension(tmp_path):
    repo = tmp_path / "ext_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    assert record.extension_id == "mystery.extension"
    assert record.workloads[0].workload_id == "mystery_v1"
    assert manager.resolve_workload("mystery_v1") is not None


def test_list_extensions_includes_entry_point_discovery(monkeypatch, tmp_path):
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    monkeypatch.setattr(
        manager,
        "_discover_entry_point_rows",
        lambda: [
            {
                "extension_id": "entrypoint.extension",
                "extension_version": "2.0.0",
                "extension_api_version": "1.0.0",
                "source": "entrypoint:demo",
                "path": str(tmp_path),
                "module": "demo_module",
                "register_callable": "register",
                "workloads": [{"workload_id": "demo_v1", "workload_version": "2.0.0"}],
            }
        ],
    )
    rows = manager.list_extensions()
    assert len(rows) == 1
    assert rows[0].extension_id == "entrypoint.extension"
    assert rows[0].workloads[0].workload_id == "demo_v1"


@pytest.mark.asyncio
async def test_run_workload_emits_provenance(tmp_path):
    repo = tmp_path / "ext_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    result = await manager.run_workload(
        workload_id="mystery_v1",
        input_config={"seed": 123},
        workspace=workspace,
        department="core",
    )

    assert result.workload_id == "mystery_v1"
    assert "provenance.json" in result.provenance_path
    assert Path(result.provenance_path).exists()
    assert (Path(result.artifact_root) / "artifact_manifest.json").exists()


@pytest.mark.asyncio
async def test_run_workload_rejects_private_orket_imports(tmp_path):
    repo = tmp_path / "blocked_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_blocked_import_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    with pytest.raises(ValueError):
        await manager.run_workload(
            workload_id="blocked_v1",
            input_config={"seed": 7},
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )
