from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Any

from orket.runtime_paths import durable_root

from .catalog import ExtensionCatalog
from .contracts import ExtensionRegistry, Workload
from .manifest_parser import ManifestParser
from .models import (
    CONTRACT_STYLE_LEGACY,
    CONTRACT_STYLE_SDK_V0,
    LEGACY_MANIFEST_FILENAME,
    RELIABLE_MODE_ENV,
    RELIABLE_REQUIRE_CLEAN_GIT_ENV,
    SDK_MANIFEST_FILENAMES,
    ExtensionRecord,
    ExtensionRunResult,
    LoadedManifest,
    WorkloadRecord,
    default_extensions_catalog_path,
)
from .reproducibility import ReproducibilityEnforcer
from .workload_executor import WorkloadExecutor

_LoadedManifest = LoadedManifest


class _WorkloadRegistry(ExtensionRegistry):
    def __init__(self) -> None:
        self._workloads: dict[str, Workload] = {}

    def register_workload(self, workload: Workload) -> None:
        workload_id = str(getattr(workload, "workload_id", "") or "").strip()
        if not workload_id:
            raise ValueError("workload_id is required")
        self._workloads[workload_id] = workload

    def workloads(self) -> dict[str, Workload]:
        return dict(self._workloads)


class ExtensionManager:
    """Coordinator for extension catalog, installation, and workload execution."""

    def __init__(self, catalog_path: Path | None = None, project_root: Path | None = None):
        self.catalog_path = (catalog_path or default_extensions_catalog_path()).resolve()
        self.project_root = (project_root or Path.cwd()).resolve()
        self.install_root = durable_root() / "extensions"
        self.install_root.mkdir(parents=True, exist_ok=True)

        self.catalog = ExtensionCatalog(self.catalog_path)
        self.manifest_parser = ManifestParser()
        self.reproducibility = ReproducibilityEnforcer(self.project_root)
        self.workload_executor = WorkloadExecutor(
            project_root=self.project_root,
            reproducibility=self.reproducibility,
            registry_factory=_WorkloadRegistry,
        )

    def __getattr__(self, name: str) -> Any:
        delegated = {
            "_load_catalog_payload": self.catalog.load_catalog_payload,
            "_save_catalog_payload": self.catalog.save_catalog_payload,
            "_row_from_record": self.catalog.row_from_record,
            "_discover_entry_point_rows": self.catalog.discover_entry_point_rows,
            "_load_manifest": self.manifest_parser.load_manifest,
            "_record_from_manifest": self.manifest_parser.record_from_manifest,
            "_legacy_record_from_manifest": self.manifest_parser.legacy_record_from_manifest,
            "_sdk_record_from_manifest": self.manifest_parser.sdk_record_from_manifest,
            "_run_legacy_workload": self.workload_executor.run_legacy_workload,
            "_run_sdk_workload": self.workload_executor.run_sdk_workload,
            "_load_legacy_workload": self.workload_executor.loader.load_legacy_workload,
            "_load_sdk_workload": self.workload_executor.loader.load_sdk_workload,
            "_parse_sdk_entrypoint": self.workload_executor.loader.parse_sdk_entrypoint,
            "_validate_extension_imports": self.workload_executor.loader.validate_extension_imports,
            "_build_sdk_capability_registry": self.workload_executor.artifacts.build_sdk_capability_registry,
            "_validate_sdk_artifacts": self.workload_executor.artifacts.validate_sdk_artifacts,
            "_artifact_root": self.workload_executor.artifacts.artifact_root,
            "_run_validators": self.workload_executor.artifacts.run_validators,
            "_build_provenance": self.workload_executor.artifacts.build_provenance,
            "_build_sdk_provenance": self.workload_executor.artifacts.build_sdk_provenance,
            "_build_artifact_manifest": self.workload_executor.artifacts.build_artifact_manifest,
            "_reliable_mode_enabled": self.reproducibility.reliable_mode_enabled,
            "_validate_required_materials": self.reproducibility.validate_required_materials,
            "_validate_clean_git_if_required": self.reproducibility.validate_clean_git_if_required,
        }
        target = delegated.get(name)
        if target is not None:
            return target
        raise AttributeError(name)

    def list_extensions(self) -> list[ExtensionRecord]:
        rows = self._discover_entry_point_rows()
        return self.catalog.list_extensions(entry_point_rows=rows)

    def resolve_workload(self, workload_id: str) -> tuple[ExtensionRecord, WorkloadRecord] | None:
        return self.catalog.resolve_workload(workload_id, entry_point_rows=self._discover_entry_point_rows())

    def install_from_repo(self, repo: str, ref: str | None = None) -> ExtensionRecord:
        repo_value = str(repo or "").strip()
        if not repo_value:
            raise ValueError("repo is required")
        ref_value = str(ref or "").strip()

        source_hash = hashlib.sha256(f"{repo_value}@{ref_value}".encode("utf-8")).hexdigest()[:12]
        leaf = f"{Path(repo_value).stem or 'extension'}-{source_hash}"
        destination = self.install_root / leaf
        if destination.exists():
            shutil.rmtree(destination)

        self._run_command(["git", "clone", repo_value, str(destination)], cwd=self.project_root)
        if ref_value:
            self._run_command(["git", "checkout", ref_value], cwd=destination)

        loaded = self._load_manifest(destination)
        record = self._record_from_manifest(
            loaded.payload,
            source=repo_value,
            path=destination,
            contract_style=loaded.contract_style,
            manifest_path=loaded.manifest_path,
        )
        payload = self._load_catalog_payload()
        rows = [
            row
            for row in payload.get("extensions", [])
            if str(row.get("extension_id", "")).strip() != record.extension_id
        ]
        rows.append(self._row_from_record(record))
        self._save_catalog_payload({"extensions": rows})
        return record

    async def run_workload(
        self,
        *,
        workload_id: str,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
    ) -> ExtensionRunResult:
        resolved = self.resolve_workload(workload_id)
        if resolved is None:
            raise ValueError(f"Unknown workload '{workload_id}'")
        extension, workload_record = resolved

        if workload_record.contract_style == CONTRACT_STYLE_SDK_V0 or extension.contract_style == CONTRACT_STYLE_SDK_V0:
            return await self._run_sdk_workload(
                extension=extension,
                workload=workload_record,
                input_config=input_config,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
        return await self._run_legacy_workload(
            extension=extension,
            workload_id=workload_id,
            input_config=input_config,
            workspace=workspace,
            department=department,
            interaction_context=interaction_context,
        )

    @staticmethod
    def _run_command(command: list[str], *, cwd: Path) -> None:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\\nstdout={result.stdout.strip()}\\nstderr={result.stderr.strip()}"
            )


__all__ = [
    "CONTRACT_STYLE_LEGACY",
    "CONTRACT_STYLE_SDK_V0",
    "LEGACY_MANIFEST_FILENAME",
    "RELIABLE_MODE_ENV",
    "RELIABLE_REQUIRE_CLEAN_GIT_ENV",
    "SDK_MANIFEST_FILENAMES",
    "ExtensionManager",
    "ExtensionRecord",
    "ExtensionRunResult",
    "WorkloadRecord",
    "_LoadedManifest",
]
