from __future__ import annotations

import json
from pathlib import Path

from orket.extensions.catalog import ExtensionCatalog
from orket.extensions.manifest_parser import ManifestParser
from orket.extensions.models import CONTRACT_STYLE_LEGACY, ExtensionRecord, WorkloadRecord
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.extensions.workload_executor import WorkloadExecutor
from orket.extensions.workload_loader import WorkloadLoader
from orket.extensions.contracts import RunPlan


def test_extension_catalog_load_and_list(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    payload = {
        "extensions": [
            {
                "extension_id": "demo.ext",
                "extension_version": "1.2.3",
                "source": "git+demo",
                "workloads": [{"workload_id": "demo_v1", "workload_version": "1.0.0"}],
            }
        ]
    }
    catalog_path.write_text(json.dumps(payload), encoding="utf-8")

    catalog = ExtensionCatalog(catalog_path)
    records = catalog.list_extensions()

    assert len(records) == 1
    assert records[0].extension_id == "demo.ext"
    assert records[0].workloads[0].workload_id == "demo_v1"


def test_manifest_parser_load_manifest_legacy(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "orket_extension.json").write_text(
        json.dumps(
            {
                "extension_id": "demo.ext",
                "extension_version": "0.1.0",
                "module": "demo_module",
                "workloads": [{"workload_id": "demo_v1", "workload_version": "0.1.0"}],
            }
        ),
        encoding="utf-8",
    )

    parser = ManifestParser()
    loaded = parser.load_manifest(repo)

    assert loaded.contract_style == CONTRACT_STYLE_LEGACY
    record = parser.record_from_manifest(
        loaded.payload,
        source="demo",
        path=repo,
        contract_style=loaded.contract_style,
        manifest_path=loaded.manifest_path,
    )
    assert record.extension_id == "demo.ext"


def test_reproducibility_enforcer_reliable_mode_enabled_default(tmp_path: Path) -> None:
    enforcer = ReproducibilityEnforcer(tmp_path)
    assert enforcer.reliable_mode_enabled() is True


def test_workload_loader_parse_sdk_entrypoint() -> None:
    loader = WorkloadLoader(registry_factory=lambda: None)  # type: ignore[arg-type]
    module_name, attr_name = loader.parse_sdk_entrypoint("demo.module:run")
    assert module_name == "demo.module"
    assert attr_name == "run"


def test_workload_artifacts_build_manifest(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir(parents=True)
    (artifact_root / "a.txt").write_text("hello", encoding="utf-8")

    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    manifest = artifacts.build_artifact_manifest(artifact_root)

    assert manifest["files"][0]["path"] == "a.txt"
    assert len(manifest["manifest_sha256"]) == 64


def test_workload_executor_compile_workload() -> None:
    class _Workload:
        workload_id = "demo_v1"
        workload_version = "1.0.0"

        def compile(self, input_config):
            return RunPlan(workload_id="demo_v1", workload_version="1.0.0", actions=())

    executor = WorkloadExecutor(
        project_root=Path.cwd(),
        reproducibility=ReproducibilityEnforcer(Path.cwd()),
        registry_factory=lambda: None,  # type: ignore[arg-type]
    )
    run_plan = executor._compile_workload(_Workload(), {"seed": 1}, None)
    assert run_plan.workload_id == "demo_v1"
