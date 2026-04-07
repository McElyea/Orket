from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from orket.application.services.config_precedence_resolver import ConfigPrecedenceResolver
from orket.extensions.manager import ExtensionManager


async def _path_exists(path: Path) -> bool:
    return await asyncio.to_thread(path.exists)


async def _read_json_file(path: Path) -> dict:
    content = await asyncio.to_thread(path.read_text, encoding="utf-8")
    return json.loads(content)


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


def _init_sdk_extension_repo(repo_root, *, required_capabilities=None, config_sections=None, allowed_stdlib_modules=None):
    required_capabilities = list(required_capabilities or [])
    allowed_stdlib_modules = ["hashlib", "pathlib"] if allowed_stdlib_modules is None else allowed_stdlib_modules
    config_lines = [f"  - {section}" for section in list(config_sections or [])]
    config_section_lines = ["config_sections:", *config_lines] if config_lines else ["config_sections: []"]
    stdlib_lines = [f"  - {module}" for module in list(allowed_stdlib_modules or [])]
    stdlib_section_lines = ["allowed_stdlib_modules:", *stdlib_lines] if stdlib_lines else ["allowed_stdlib_modules: []"]
    (repo_root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: sdk.extension",
                "extension_version: 0.1.0",
                *config_section_lines,
                *stdlib_section_lines,
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


def _init_sdk_dynamic_import_repo(repo_root):
    (repo_root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: sdk.dynamic.import",
                "extension_version: 0.1.0",
                "allowed_stdlib_modules:",
                "  - pathlib",
                "workloads:",
                "  - workload_id: sdk_dynamic_import_v1",
                "    entrypoint: sdk_dynamic_extension:run_workload",
                "    required_capabilities: []",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "sdk_dynamic_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from pathlib import Path",
                "from orket_extension_sdk import WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                "    _ = Path(ctx.output_dir)",
                "    __import__('subprocess')",
                "    return WorkloadResult(ok=True, output={'unexpected': 'ran'})",
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
        "allowed_stdlib_modules": ["hashlib", "pathlib"],
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
        "allowed_stdlib_modules": ["hashlib", "pathlib"],
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


def _assert_governed_identity(result) -> None:
    provenance_path = Path(result.provenance_path)
    artifact_manifest_path = Path(result.artifact_manifest_path)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))

    assert result.claim_tier == "non_deterministic_lab_only"
    assert result.compare_scope == "extension_workload_provenance_family_v1"
    assert result.operator_surface == "extension_run_result_identity_v1"
    assert result.policy_digest.startswith("sha256:")
    assert result.control_bundle_hash.startswith("sha256:")
    assert result.artifact_manifest_hash == f"sha256:{artifact_manifest['manifest_sha256']}"
    assert result.provenance_hash.startswith("sha256:")
    assert result.determinism_class == "workspace"

    assert provenance["claim_tier"] == result.claim_tier
    assert provenance["compare_scope"] == result.compare_scope
    assert provenance["operator_surface"] == "extension_provenance_v1"
    assert provenance["policy_digest"] == result.policy_digest
    assert provenance["control_bundle_hash"] == result.control_bundle_hash
    assert provenance["artifact_manifest_ref"] == "artifact_manifest.json"
    assert provenance["artifact_manifest_hash"] == result.artifact_manifest_hash
    assert provenance["provenance_ref"] == "provenance.json"
    assert provenance["determinism_class"] == result.determinism_class
    assert provenance["control_bundle"]["input_identity"] == result.plan_hash
    control_plane_workload_record = provenance["control_plane_workload_record"]
    assert result.control_plane_workload_record == control_plane_workload_record
    assert control_plane_workload_record["workload_id"] == result.workload_id
    assert control_plane_workload_record["output_contract_ref"] == "extension_run_result_identity_v1"
    assert control_plane_workload_record["workload_digest"].startswith("sha256:")

    assert artifact_manifest["claim_tier"] == result.claim_tier
    assert artifact_manifest["compare_scope"] == result.compare_scope
    assert artifact_manifest["operator_surface"] == "extension_artifact_manifest_v1"
    assert artifact_manifest["policy_digest"] == result.policy_digest
    assert artifact_manifest["control_bundle_hash"] == result.control_bundle_hash
    assert artifact_manifest["plan_hash"] == result.plan_hash
    assert artifact_manifest["provenance_ref"] == "provenance.json"
    assert artifact_manifest["determinism_class"] == result.determinism_class


def test_list_extensions_from_catalog(tmp_path):
    """Layer: unit. Verifies installed extension catalog rows are read from manifest-entry storage."""
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "manifest_entries": [
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
    assert extensions[0].manifest_entries[0].workload_id == "mystery_v1"


def test_resolve_manifest_entry_returns_extension_and_workload(tmp_path):
    """Layer: unit. Verifies manifest-entry lookup works against installed catalog rows."""
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "mystery.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/repo.git",
                        "manifest_entries": [
                            {"workload_id": "mystery_v1", "workload_version": "1.0.0"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = ExtensionManager(catalog_path=catalog)
    resolved = manager._resolve_manifest_entry("mystery_v1")

    assert resolved is not None
    extension, workload = resolved
    assert extension.extension_id == "mystery.extension"
    assert workload.workload_id == "mystery_v1"


def test_uses_sdk_contract_reflects_manifest_style(tmp_path):
    """Layer: unit. Verifies manager exposes SDK eligibility as a boolean probe instead of leaking manifest metadata."""
    catalog = tmp_path / "extensions_catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": "legacy.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/legacy.git",
                        "contract_style": "legacy_v1",
                        "manifest_entries": [{"workload_id": "legacy_v1", "workload_version": "1.0.0"}],
                    },
                    {
                        "extension_id": "sdk.extension",
                        "extension_version": "1.0.0",
                        "source": "git+https://example/sdk.git",
                        "contract_style": "sdk_v0",
                        "manifest_entries": [{"workload_id": "sdk_v1", "workload_version": "1.0.0"}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    manager = ExtensionManager(catalog_path=catalog)

    assert manager.has_manifest_entry("legacy_v1") is True
    assert manager.uses_sdk_contract("legacy_v1") is False
    assert manager.has_manifest_entry("sdk_v1") is True
    assert manager.uses_sdk_contract("sdk_v1") is True
    assert manager.has_manifest_entry("missing_v1") is False
    assert manager.uses_sdk_contract("missing_v1") is False


def test_install_from_repo_registers_extension(tmp_path):
    repo = tmp_path / "ext_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    assert record.extension_id == "mystery.extension"
    assert record.manifest_entries[0].workload_id == "mystery_v1"
    assert len(record.resolved_commit_sha) == 40
    assert len(record.manifest_digest_sha256) == 64
    assert record.trust_profile == "production"
    assert record.security_mode == "compat"
    assert record.security_profile == "production"
    assert len(record.security_policy_version) == 64
    assert record.installed_at_utc
    assert manager._resolve_manifest_entry("mystery_v1") is not None


def test_install_from_repo_registers_sdk_extension(tmp_path):
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    original_sections = set(ConfigPrecedenceResolver.SECTION_KEYS)
    _init_sdk_extension_repo(repo, config_sections=["appearance"], allowed_stdlib_modules=["hashlib", "pathlib"])

    try:
        manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
        record = manager.install_from_repo(str(repo))
        assert "appearance" in ConfigPrecedenceResolver.SECTION_KEYS
    finally:
        ConfigPrecedenceResolver.SECTION_KEYS = original_sections

    assert record.extension_id == "sdk.extension"
    assert record.contract_style == "sdk_v0"
    assert record.config_sections == ("appearance",)
    assert record.allowed_stdlib_modules == ("hashlib", "pathlib")
    assert record.manifest_entries[0].workload_id == "sdk_v1"
    assert record.manifest_entries[0].entrypoint == "sdk_extension:run_workload"
    assert len(record.resolved_commit_sha) == 40
    assert len(record.manifest_digest_sha256) == 64
    assert len(record.security_policy_version) == 64


@pytest.mark.asyncio
async def test_run_sdk_workload_blocks_undeclared_stdlib_import_when_declared_allowlist_exists(tmp_path):
    """Layer: integration. Verifies declared stdlib import sandboxing blocks undeclared runtime imports."""
    repo = tmp_path / "sdk_repo_stdlib"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo, allowed_stdlib_modules=["pathlib"])
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    with pytest.raises(ValueError, match="E_EXT_STDLIB_IMPORT_UNDECLARED: hashlib"):
        await manager.run_workload(
            workload_id="sdk_v1",
            input_config={"seed": 321, "mode": "basic"},
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )


@pytest.mark.asyncio
async def test_run_sdk_workload_subprocess_blocks_dynamic_undeclared_stdlib_import(tmp_path):
    """Layer: integration. Verifies subprocess import-hook sandboxing catches dynamic stdlib imports."""
    repo = tmp_path / "sdk_repo_dynamic"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_dynamic_import_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    with pytest.raises(RuntimeError, match="E_EXT_STDLIB_IMPORT_UNDECLARED: subprocess"):
        await manager.run_workload(
            workload_id="sdk_dynamic_import_v1",
            input_config={"seed": 321, "mode": "basic"},
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )


def test_install_from_repo_registers_sdk_json_manifest_extension(tmp_path):
    repo = tmp_path / "sdk_json_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo_json_manifest(repo)

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    assert record.extension_id == "sdk.json.extension"
    assert record.contract_style == "sdk_v0"
    assert record.manifest_entries[0].workload_id == "sdk_json_v1"
    assert record.manifest_entries[0].entrypoint == "sdk_json_extension:JsonWorkload"


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
    assert rows[0].manifest_entries[0].workload_id == "demo_v1"


def test_extension_manager_exposes_helper_methods_explicitly():
    """Layer: unit. Verifies helper methods are statically discoverable instead of hidden behind `__getattr__`."""
    explicit_helpers = {
        "_discover_entry_point_rows",
        "_load_manifest",
        "_record_from_manifest",
        "_run_legacy_workload",
        "_run_sdk_workload",
        "_resolve_manifest_entry",
        "_validate_extension_imports",
        "uses_sdk_contract",
    }
    assert explicit_helpers.issubset(ExtensionManager.__dict__)


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
    assert await _path_exists(Path(result.provenance_path))
    assert await _path_exists(Path(result.artifact_root) / "artifact_manifest.json")
    _assert_governed_identity(result)


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
    turn_final_payload = next(payload for name, payload in ctx.events if name == "turn_final")
    assert turn_final_payload["authoritative"] is True
    assert turn_final_payload["summary"]
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
    assert await _path_exists(Path(result.provenance_path))
    assert await _path_exists(Path(result.artifact_root) / "result.txt")
    assert await _path_exists(Path(result.artifact_root) / "artifact_manifest.json")
    provenance = await _read_json_file(Path(result.provenance_path))
    assert provenance["extension"]["resolved_commit_sha"] == manager._resolve_manifest_entry("sdk_v1")[0].resolved_commit_sha
    assert provenance["extension"]["manifest_digest_sha256"] == manager._resolve_manifest_entry("sdk_v1")[0].manifest_digest_sha256
    assert provenance["security"]["mode"] == "compat"
    assert provenance["security"]["profile"] == "production"
    assert isinstance(provenance["security"]["policy_version"], str)
    assert provenance["security"]["compat_fallback_count"] >= 0
    assert provenance["input_config"] == {}
    assert provenance["run_result"] == {}
    assert provenance["summary"] == {}
    assert provenance["input_config_redacted"]["item_count"] >= 1
    assert "payload_digest_sha256" in provenance["run_result_redacted"]
    assert "payload_digest_sha256" in provenance["summary_redacted"]
    _assert_governed_identity(result)


@pytest.mark.asyncio
async def test_run_sdk_workload_provenance_verbose_mode_includes_raw_payloads(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_EXT_PROVENANCE_VERBOSE", "true")
    repo = tmp_path / "sdk_repo_verbose"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    result = await manager.run_workload(
        workload_id="sdk_v1",
        input_config={"seed": 33, "mode": "verbose"},
        workspace=workspace,
        department="core",
    )
    provenance = await _read_json_file(Path(result.provenance_path))
    assert provenance["input_config"]["seed"] == 33
    assert provenance["run_result"]["status"] in {"ok", "error"}
    assert provenance["summary"]["artifact_count"] >= 1


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
    assert await _path_exists(Path(legacy_result.provenance_path))
    assert await _path_exists(Path(sdk_result.provenance_path))


@pytest.mark.asyncio
async def test_run_sdk_workload_blocks_artifact_path_escape(tmp_path):
    repo = tmp_path / "sdk_bad_escape_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_bad_artifact_repo(repo, mode="escape")
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="E_ARTIFACT_PATH_TRAVERSAL"):
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


@pytest.mark.asyncio
async def test_run_workload_rejects_manifest_digest_tamper(tmp_path):
    repo = tmp_path / "sdk_repo_tamper"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_extension_repo(repo)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))

    manifest_path = Path(record.manifest_path)
    await asyncio.to_thread(
        manifest_path.write_text,
        "manifest_version: v0\nextension_id: sdk.extension\nextension_version: 9.9.9\n",
        encoding="utf-8",
    )

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    with pytest.raises(RuntimeError, match="E_EXT_MANIFEST_DIGEST_MISMATCH"):
        await manager.run_workload(
            workload_id="sdk_v1",
            input_config={"seed": 8},
            workspace=workspace,
            department="core",
        )


def test_install_from_repo_enforce_mode_blocks_local_path(tmp_path, monkeypatch):
    repo = tmp_path / "ext_repo_enforce"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_SOURCE_LOCAL_PATH_DENIED"):
        manager.install_from_repo(str(repo))


def test_install_from_repo_compat_mode_records_fallbacks(tmp_path, monkeypatch):
    repo = tmp_path / "ext_repo_compat"
    repo.mkdir(parents=True, exist_ok=True)
    _init_test_extension_repo(repo)
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "compat")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")

    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    record = manager.install_from_repo(str(repo))
    assert "EXT_LOCAL_PATH_COMPAT" in record.compat_fallbacks


def test_source_policy_enforce_denies_unapproved_host(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_HOST_DENIED"):
        ExtensionManager._evaluate_source_policy("https://example.com/repo.git")


def test_source_policy_enforce_denies_unapproved_protocol(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    with pytest.raises(RuntimeError, match="E_EXT_TRUST_PROTOCOL_DENIED"):
        ExtensionManager._evaluate_source_policy("http://github.com/repo.git")


def test_source_policy_compat_records_host_and_protocol_fallbacks(monkeypatch):
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "compat")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    monkeypatch.setenv("ORKET_EXT_ALLOWED_HOSTS", "github.com")
    decision = ExtensionManager._evaluate_source_policy("http://example.com/repo.git")
    assert decision.security_mode == "compat"
    assert "EXT_PROTOCOL_COMPAT" in decision.compat_fallbacks
    assert "EXT_HOST_COMPAT" in decision.compat_fallbacks
