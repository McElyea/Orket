from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest

from orket.extensions.manager import ExtensionManager
from orket.interfaces.cli import _install_extension, _print_extensions_list, _run_extension_workload


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
                "from orket.extensions import RunPlan",
                "",
                "class MysteryWorkload:",
                "    workload_id = 'mystery_v1'",
                "    workload_version = '1.0.0'",
                "",
                "    def compile(self, input_config):",
                "        return RunPlan(workload_id='mystery_v1', workload_version='1.0.0', actions=())",
                "",
                "    def validators(self):",
                "        return []",
                "",
                "    def summarize(self, run_artifacts):",
                "        return {'ok': True}",
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


def test_print_extensions_list_shows_installed_extensions(tmp_path, capsys):
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

    _print_extensions_list(manager)
    out = capsys.readouterr().out

    assert "Installed extensions:" in out
    assert "mystery.extension (1.0.0)" in out
    assert "workload: mystery_v1 (1.0.0)" in out


@pytest.mark.asyncio
async def test_run_extension_workload_requires_registered_workload(tmp_path):
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json")
    args = SimpleNamespace(subcommand="missing_workload", seed=123, workspace=str(tmp_path / "workspace"), department="core")

    with pytest.raises(ValueError):
        await _run_extension_workload(args, manager)


@pytest.mark.asyncio
async def test_run_extension_workload_executes_installed_workload(tmp_path, capsys):
    repo = tmp_path / "ext_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)

    install_args = SimpleNamespace(target=str(repo), ref=None)
    _install_extension(install_args, manager)

    args = SimpleNamespace(
        subcommand="mystery_v1",
        seed=123,
        workspace=str(tmp_path / "workspace" / "default"),
        department="core",
    )
    await _run_extension_workload(args, manager)
    out = capsys.readouterr().out
    assert "Executed workload: mystery_v1 (1.0.0)" in out
