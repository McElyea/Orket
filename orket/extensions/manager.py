from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from copy import deepcopy
from functools import partial
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.extension_install_store import sha256_file
from orket.application.services.control_plane_workload_catalog import (
    _resolve_extension_control_plane_workload,
)
from orket.runtime_paths import durable_root
from orket_extension_sdk.capabilities import CapabilityRegistry

from .catalog import ExtensionCatalog
from .contracts import ExtensionRegistry, Workload
from .controller_dispatcher_contract import ERROR_CHILD_SDK_REQUIRED
from .git_commands import observe_commit_in_worker
from .governed_agent_catalog import resolve_governed_agent_catalog_entry
from .installation import install_extension
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
    default_extensions_catalog_path,
    utc_now_iso,
)
from .reproducibility import ReproducibilityEnforcer
from .workload_executor import WorkloadExecutor
from .workload_policy import capture_workload_policy

if TYPE_CHECKING:
    from .models import GovernedAgentWorkloadLaunch, _ExtensionManifestEntry

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

    def __init__(self, catalog_path: Path | None = None, project_root: Path | None = None,
                 *, utc_now: Callable[[], str] = utc_now_iso, invocation_root: Path | None = None,
                 environment: Mapping[str, str] | None = None):
        root = invocation_root or Path.cwd()
        observed = dict(os.environ if environment is None else environment)
        if not root.is_absolute():
            raise ValueError("E_EXT_INVOCATION_ROOT_ABSOLUTE_REQUIRED")
        catalog = catalog_path or default_extensions_catalog_path(invocation_root=root, environment=observed)
        self.catalog_path = (root / catalog).resolve()
        self.project_root = (root / (project_root or root)).resolve()
        self.install_root = durable_root(invocation_root=root, environment=observed) / "extensions"
        self._utc_now = utc_now
        self._config_sections: set[str] = set()
        self._config_sections_lock = Lock()

        self.catalog = ExtensionCatalog(self.catalog_path)
        self.manifest_parser = ManifestParser()
        self.reproducibility = ReproducibilityEnforcer(self.project_root)
        self.workload_executor = WorkloadExecutor(
            project_root=self.project_root,
            reproducibility=self.reproducibility,
            registry_factory=_WorkloadRegistry,
        )

    def _load_catalog_payload(self) -> dict[str, Any]:
        return self.catalog.load_catalog_payload()

    def _save_catalog_payload(self, *args: Any, **kwargs: Any) -> None:
        self.catalog.save_catalog_payload(*args, **kwargs)

    def _row_from_record(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.catalog.row_from_record(*args, **kwargs)

    def _discover_entry_point_rows(self) -> list[dict[str, Any]]:
        return self.catalog.discover_entry_point_rows()

    def _load_manifest(self, *args: Any, **kwargs: Any) -> LoadedManifest:
        return self.manifest_parser.load_manifest(*args, **kwargs)

    def _record_from_manifest(self, *args: Any, **kwargs: Any) -> ExtensionRecord:
        return self.manifest_parser.record_from_manifest(*args, **kwargs)

    def _legacy_record_from_manifest(self, *args: Any, **kwargs: Any) -> ExtensionRecord:
        return self.manifest_parser.legacy_record_from_manifest(*args, **kwargs)

    def _sdk_record_from_manifest(self, *args: Any, **kwargs: Any) -> ExtensionRecord:
        return self.manifest_parser.sdk_record_from_manifest(*args, **kwargs)

    async def _run_legacy_workload(self, *args: Any, **kwargs: Any) -> ExtensionRunResult:
        return await self.workload_executor.run_legacy_workload(*args, **kwargs)

    async def _run_sdk_workload(self, *args: Any, **kwargs: Any) -> ExtensionRunResult:
        return await self.workload_executor.run_sdk_workload(*args, **kwargs)

    def _load_legacy_workload(self, *args: Any, **kwargs: Any) -> Any:
        return self.workload_executor.loader.load_legacy_workload(*args, **kwargs)

    def _load_sdk_workload(self, *args: Any, **kwargs: Any) -> Any:
        return self.workload_executor.loader.load_sdk_workload(*args, **kwargs)

    def _parse_sdk_entrypoint(self, *args: Any, **kwargs: Any) -> tuple[str, str]:
        return self.workload_executor.loader.parse_sdk_entrypoint(*args, **kwargs)

    def _validate_extension_imports(self, *args: Any, **kwargs: Any) -> None:
        self.workload_executor.loader.validate_extension_imports(*args, **kwargs)

    def _build_sdk_capability_registry(self, *args: Any, **kwargs: Any) -> CapabilityRegistry:
        return self.workload_executor.artifacts.build_sdk_capability_registry(*args, **kwargs)

    def _validate_sdk_artifacts(self, *args: Any, **kwargs: Any) -> None:
        self.workload_executor.artifacts.validate_sdk_artifacts(*args, **kwargs)

    def _artifact_root(self, *args: Any, **kwargs: Any) -> Path:
        return self.workload_executor.artifacts.artifact_root(*args, **kwargs)

    def _run_validators(self, *args: Any, **kwargs: Any) -> list[str]:
        return self.workload_executor.artifacts.run_validators(*args, **kwargs)

    def _build_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_provenance(*args, **kwargs)

    def _build_sdk_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_sdk_provenance(*args, **kwargs)

    def _build_artifact_manifest(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_artifact_manifest(*args, **kwargs)

    def _validate_required_materials(self, *args: Any, **kwargs: Any) -> None:
        self.reproducibility.validate_required_materials(*args, **kwargs)

    def list_extensions(self) -> list[ExtensionRecord]:
        records = self.catalog.list_extensions(entry_point_rows=self._discover_entry_point_rows())
        for record in records:
            self._remember_config_sections(record)
        return records

    def config_sections(self) -> tuple[str, ...]:
        with self._config_sections_lock:
            return tuple(sorted(self._config_sections))

    def has_manifest_entry(self, workload_id: str) -> bool:
        return self._resolve_manifest_entry(workload_id) is not None

    def required_capabilities_for_workload(self, workload_id: str) -> tuple[str, ...]:
        resolved = self._resolve_manifest_entry(workload_id)
        if resolved is None:
            raise ValueError(f"Unknown workload '{workload_id}'")
        _, workload = resolved
        return tuple(workload.required_capabilities)

    def uses_sdk_contract(self, workload_id: str) -> bool:
        return bool(
            (resolved := self._resolve_manifest_entry(workload_id))
            and CONTRACT_STYLE_SDK_V0 in {resolved[0].contract_style, resolved[1].contract_style}
        )

    def resolve_governed_agent_workload(self, workload_id: str) -> GovernedAgentWorkloadLaunch:
        return resolve_governed_agent_catalog_entry(self, workload_id)

    def _resolve_manifest_entry(self, workload_id: str) -> tuple[ExtensionRecord, _ExtensionManifestEntry] | None:
        return self.catalog._resolve_manifest_entry(workload_id, entry_point_rows=self._discover_entry_point_rows())

    def _resolve_control_plane_workload_record(
        self,
        *,
        extension: ExtensionRecord,
        workload: _ExtensionManifestEntry,
    ) -> dict[str, Any]:
        return _resolve_extension_control_plane_workload(
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            extension_id=extension.extension_id,
            extension_version=extension.extension_version,
            entrypoint=workload.entrypoint,
            required_capabilities=workload.required_capabilities,
            contract_style=workload.contract_style or extension.contract_style,
            manifest_digest_sha256=extension.manifest_digest_sha256,
        ).model_dump(mode="json")

    async def install_from_repo(self, repo: str, ref: str | None = None) -> ExtensionRecord:
        environment, installed_at_utc = dict(os.environ), self._utc_now()
        record = await install_extension(
            repo=repo, ref=ref or "", install_root=self.install_root, project_root=self.project_root,
            catalog=self.catalog, parser=self.manifest_parser, environment=environment,
            installed_at_utc=installed_at_utc)
        self._remember_config_sections(record)
        return record

    def _remember_config_sections(self, record: ExtensionRecord) -> None:
        sections = {str(section).strip() for section in record.config_sections if str(section or "").strip()}
        with self._config_sections_lock:
            self._config_sections.update(sections)

    async def run_workload(
        self,
        *,
        workload_id: str,
        input_config: dict[str, Any],
        workspace: Path,
        department: str,
        interaction_context: Any | None = None,
        require_sdk: bool = False,
    ) -> ExtensionRunResult:
        policy, captured = capture_workload_policy(), deepcopy(input_config)
        environment = dict(os.environ)
        extension, workload_record, control_plane_workload_record = await run_owned_thread(
            partial(self._prepare_workload, workload_id, environment, require_sdk=require_sdk),
            label="extension-workload-preflight")

        if workload_record.contract_style == CONTRACT_STYLE_SDK_V0 or extension.contract_style == CONTRACT_STYLE_SDK_V0:
            return await self._run_sdk_workload(
                extension=extension,
                workload=workload_record,
                control_plane_workload_record=control_plane_workload_record,
                input_config=captured,
                policy=policy,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
        return await self._run_legacy_workload(
            extension=extension,
            workload=workload_record,
            control_plane_workload_record=control_plane_workload_record,
            input_config=captured,
            policy=policy,
            workspace=workspace,
            department=department,
            interaction_context=interaction_context,
        )

    def _prepare_workload(self, workload_id: str, environment: dict[str, str], *, require_sdk: bool):
        resolved = self._resolve_manifest_entry(workload_id)
        if resolved is None:
            raise ValueError(f"Unknown workload '{workload_id}'")
        extension, workload = resolved
        if require_sdk and CONTRACT_STYLE_SDK_V0 not in {extension.contract_style, workload.contract_style}:
            raise ValueError(ERROR_CHILD_SDK_REQUIRED)
        self._verify_extension_integrity(extension, environment=environment)
        return extension, workload, self._resolve_control_plane_workload_record(extension=extension, workload=workload)

    def _verify_extension_integrity(self, extension: ExtensionRecord, *, environment: dict[str, str] | None = None) -> None:
        extension_path = Path(extension.path).resolve()
        manifest_path_raw = str(extension.manifest_path or "").strip()
        if extension.resolved_commit_sha:
            # Explicit --git-dir refuses missing/broken metadata instead of discovering a parent repository.
            current = observe_commit_in_worker(extension_path, "HEAD",
                                               environment=dict(os.environ) if environment is None else environment)
            if current != extension.resolved_commit_sha:
                raise RuntimeError("E_EXT_COMMIT_MISMATCH")
        if manifest_path_raw and extension.manifest_digest_sha256:
            manifest_path = Path(manifest_path_raw).resolve()
            current_digest = sha256_file(manifest_path)
            if current_digest != extension.manifest_digest_sha256:
                raise RuntimeError("E_EXT_MANIFEST_DIGEST_MISMATCH")



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
    "_LoadedManifest",
]
