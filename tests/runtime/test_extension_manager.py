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


def _init_sdk_extension_repo(repo_root, *, required_capabilities=None):
    required_capabilities = list(required_capabilities or [])
    (repo_root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: sdk.extension",
                "extension_version: 0.1.0",
                "workloads:",
                "  - workload_id: sdk_v1",
                "    entrypoint: sdk_extension:run_workload",
                f"    required_capabilities: {json.dumps(required_capabilities)}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "sdk_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import hashlib",
                "from pathlib import Path",
                "from orket_extension_sdk import ArtifactRef, WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                "    out_path = Path(ctx.output_dir) / 'result.txt'",
                "    text = f\"seed={ctx.seed};mode={payload.get('mode', 'na')}\"",
                "    out_path.write_text(text, encoding='utf-8')",
                "    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()",
                "    return WorkloadResult(",
                "        ok=True,",
                "        output={'seed': ctx.seed, 'mode': payload.get('mode', 'na')},",
                "        artifacts=[ArtifactRef(path='result.txt', digest_sha256=digest, kind='text')],",
                "    )",
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


def _init_sdk_extension_repo_json_manifest(repo_root):
    manifest = {
        "manifest_version": "v0",
        "extension_id": "sdk.json.extension",
        "extension_version": "0.2.0",
        "workloads": [
            {
                "workload_id": "sdk_json_v1",
                "entrypoint": "sdk_json_extension:JsonWorkload",
                "required_capabilities": [],
            }
        ],
    }
    (repo_root / "extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "sdk_json_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import hashlib",
                "from pathlib import Path",
                "from orket_extension_sdk import ArtifactRef, WorkloadResult",
                "",
                "class JsonWorkload:",
                "    def run(self, ctx, payload):",
                "        out_path = Path(ctx.output_dir) / 'json_result.txt'",
                "        text = f\"seed={ctx.seed};label={payload.get('label', 'none')}\"",
                "        out_path.write_text(text, encoding='utf-8')",
                "        digest = hashlib.sha256(out_path.read_bytes()).hexdigest()",
                "        return WorkloadResult(",
                "            ok=True,",
                "            output={'seed': ctx.seed, 'label': payload.get('label', 'none')},",
                "            artifacts=[ArtifactRef(path='json_result.txt', digest_sha256=digest, kind='text')],",
                "        )",
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


def _init_sdk_bad_artifact_repo(repo_root, *, mode):
    module_name = f"sdk_bad_extension_{mode}"
    manifest = {
        "manifest_version": "v0",
        "extension_id": f"sdk.bad.{mode}",
        "extension_version": "0.3.0",
        "workloads": [
            {
                "workload_id": f"sdk_bad_{mode}_v1",
                "entrypoint": f"{module_name}:run_workload",
                "required_capabilities": [],
            }
        ],
    }
    (repo_root / "extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    module_lines = [
        "from __future__ import annotations",
        "from pathlib import Path",
        "import hashlib",
        "from orket_extension_sdk import ArtifactRef, WorkloadResult",
        "",
        "def run_workload(ctx, payload):",
    ]
    if mode == "escape":
        module_lines.extend(
            [
                "    out_path = Path(ctx.output_dir) / 'inside.txt'",
                "    out_path.write_text('ok', encoding='utf-8')",
                "    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()",
                "    return WorkloadResult(",
                "        ok=True,",
                "        output={'mode': 'escape'},",
                "        artifacts=[ArtifactRef(path='../outside.txt', digest_sha256=digest, kind='text')],",
                "    )",
            ]
        )
    elif mode == "digest":
        module_lines.extend(
            [
                "    out_path = Path(ctx.output_dir) / 'result.txt'",
                "    out_path.write_text('real-content', encoding='utf-8')",
                "    return WorkloadResult(",
                "        ok=True,",
                "        output={'mode': 'digest'},",
                "        artifacts=[ArtifactRef(path='result.txt', digest_sha256='0' * 64, kind='text')],",
                "    )",
            ]
        )
    else:
        raise ValueError(f"unsupported mode: {mode}")
    (repo_root / f"{module_name}.py").write_text("\n".join(module_lines), encoding="utf-8")
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


def test_install_from_repo_registers_sdk_extension(tmp_path):
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    assert record.extension_id == "sdk.extension"
    assert record.contract_style == "sdk_v0"
    assert record.workloads[0].workload_id == "sdk_v1"
    assert record.workloads[0].entrypoint == "sdk_extension:run_workload"


def test_install_from_repo_registers_sdk_json_manifest_extension(tmp_path):
    repo = tmp_path / "sdk_json_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo_json_manifest(repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    assert record.extension_id == "sdk.json.extension"
    assert record.contract_style == "sdk_v0"
    assert record.workloads[0].workload_id == "sdk_json_v1"
    assert record.workloads[0].entrypoint == "sdk_json_extension:JsonWorkload"


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


@pytest.mark.asyncio
async def test_run_workload_with_interaction_context_emits_events_and_commit(tmp_path):
    repo = tmp_path / "ext_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    class _FakeContext:
        def __init__(self):
            self.events = []
            self.commits = []

        async def emit_event(self, event_type, payload):
            self.events.append((getattr(event_type, "value", str(event_type)), payload))

        async def request_commit(self, intent):
            self.commits.append(intent)

    ctx = _FakeContext()
    result = await manager.run_workload(
        workload_id="mystery_v1",
        input_config={"seed": 1},
        workspace=tmp_path / "workspace" / "default",
        department="core",
        interaction_context=ctx,
    )
    assert result.workload_id == "mystery_v1"
    assert any(name == "model_selected" for name, _ in ctx.events)
    assert any(name == "turn_final" for name, _ in ctx.events)
    assert len(ctx.commits) == 1


@pytest.mark.asyncio
async def test_run_sdk_workload_emits_provenance(tmp_path):
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    result = await manager.run_workload(
        workload_id="sdk_v1",
        input_config={"seed": 321, "mode": "basic"},
        workspace=workspace,
        department="core",
    )

    assert result.workload_id == "sdk_v1"
    assert Path(result.provenance_path).exists()
    assert (Path(result.artifact_root) / "result.txt").exists()
    assert (Path(result.artifact_root) / "artifact_manifest.json").exists()


@pytest.mark.asyncio
async def test_run_sdk_workload_missing_required_capability_fails_closed(tmp_path):
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo, required_capabilities=["clock.now"])
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="E_SDK_CAPABILITY_MISSING"):
        await manager.run_workload(
            workload_id="sdk_v1",
            input_config={"seed": 5},
            workspace=workspace,
            department="core",
        )


@pytest.mark.asyncio
async def test_mixed_catalog_runs_legacy_and_sdk_workloads(tmp_path):
    legacy_repo = tmp_path / "legacy_repo"
    legacy_repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(legacy_repo)

    sdk_repo = tmp_path / "sdk_repo"
    sdk_repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo_json_manifest(sdk_repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(legacy_repo))
    manager.install_from_repo(str(sdk_repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)

    legacy_result = await manager.run_workload(
        workload_id="mystery_v1",
        input_config={"seed": 11},
        workspace=workspace,
        department="core",
    )
    sdk_result = await manager.run_workload(
        workload_id="sdk_json_v1",
        input_config={"seed": 12, "label": "mixed"},
        workspace=workspace,
        department="core",
    )

    assert legacy_result.workload_id == "mystery_v1"
    assert sdk_result.workload_id == "sdk_json_v1"
    assert Path(legacy_result.provenance_path).exists()
    assert Path(sdk_result.provenance_path).exists()


@pytest.mark.asyncio
async def test_run_sdk_workload_blocks_artifact_path_escape(tmp_path):
    repo = tmp_path / "sdk_bad_escape_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_bad_artifact_repo(repo, mode="escape")
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="E_SDK_ARTIFACT_ESCAPE"):
        await manager.run_workload(
            workload_id="sdk_bad_escape_v1",
            input_config={"seed": 99},
            workspace=workspace,
            department="core",
        )


@pytest.mark.asyncio
async def test_run_sdk_workload_rejects_artifact_digest_mismatch(tmp_path):
    repo = tmp_path / "sdk_bad_digest_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_bad_artifact_repo(repo, mode="digest")
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="E_SDK_ARTIFACT_DIGEST_MISMATCH"):
        await manager.run_workload(
            workload_id="sdk_bad_digest_v1",
            input_config={"seed": 100},
            workspace=workspace,
            department="core",
        )
