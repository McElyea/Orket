from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from orket.application.services.control_plane_workload_catalog import (
    WorkloadAuthorityInput,
    resolve_control_plane_workload,
)
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
    utc_now_iso,
)
from .reproducibility import ReproducibilityEnforcer
from .workload_executor import WorkloadExecutor

_LoadedManifest = LoadedManifest


@dataclass(frozen=True)
class _SourcePolicyDecision:
    security_mode: str
    security_profile: str
    security_policy_version: str
    trust_profile: str
    compat_fallbacks: tuple[str, ...]


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

    def _build_sdk_capability_registry(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_sdk_capability_registry(*args, **kwargs)

    def _validate_sdk_artifacts(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.validate_sdk_artifacts(*args, **kwargs)

    def _artifact_root(self, *args: Any, **kwargs: Any) -> Path:
        return self.workload_executor.artifacts.artifact_root(*args, **kwargs)

    def _run_validators(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.workload_executor.artifacts.run_validators(*args, **kwargs)

    def _build_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_provenance(*args, **kwargs)

    def _build_sdk_provenance(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_sdk_provenance(*args, **kwargs)

    def _build_artifact_manifest(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.workload_executor.artifacts.build_artifact_manifest(*args, **kwargs)

    def _reliable_mode_enabled(self) -> bool:
        return self.reproducibility.reliable_mode_enabled()

    def _validate_required_materials(self, *args: Any, **kwargs: Any) -> None:
        self.reproducibility.validate_required_materials(*args, **kwargs)

    def _validate_clean_git_if_required(self, *args: Any, **kwargs: Any) -> None:
        self.reproducibility.validate_clean_git_if_required(*args, **kwargs)

    def list_extensions(self) -> list[ExtensionRecord]:
        rows = self._discover_entry_point_rows()
        return self.catalog.list_extensions(entry_point_rows=rows)

    def resolve_workload(self, workload_id: str) -> tuple[ExtensionRecord, WorkloadRecord] | None:
        return self.catalog.resolve_workload(workload_id, entry_point_rows=self._discover_entry_point_rows())

    def _resolve_control_plane_workload_record(
        self,
        *,
        extension: ExtensionRecord,
        workload: WorkloadRecord,
    ) -> dict[str, Any]:
        return resolve_control_plane_workload(
            WorkloadAuthorityInput(
                kind="extension_manifest_workload",
                workload_id=workload.workload_id,
                workload_version=workload.workload_version,
                extension_id=extension.extension_id,
                extension_version=extension.extension_version,
                entrypoint=workload.entrypoint,
                required_capabilities=workload.required_capabilities,
                contract_style=workload.contract_style or extension.contract_style,
                manifest_digest_sha256=extension.manifest_digest_sha256,
            )
        ).model_dump(mode="json")

    def install_from_repo(self, repo: str, ref: str | None = None) -> ExtensionRecord:
        repo_value = str(repo or "").strip()
        if not repo_value:
            raise ValueError("repo is required")
        ref_value = str(ref or "").strip()
        policy = self._evaluate_source_policy(repo_value)

        source_hash = hashlib.sha256(f"{repo_value}@{ref_value}".encode("utf-8")).hexdigest()[:12]
        leaf = f"{Path(repo_value).stem or 'extension'}-{source_hash}"
        destination = self.install_root / leaf
        if destination.exists():
            shutil.rmtree(destination)

        self._run_command(["git", "clone", repo_value, str(destination)], cwd=self.project_root)
        resolved_commit_sha = self._resolve_commit_sha(destination, ref_value)
        self._run_command(["git", "checkout", "--detach", resolved_commit_sha], cwd=destination)

        loaded = self._load_manifest(destination)
        manifest_digest_sha256 = self._sha256_file(loaded.manifest_path)
        record = self._record_from_manifest(
            loaded.payload,
            source=repo_value,
            path=destination,
            contract_style=loaded.contract_style,
            manifest_path=loaded.manifest_path,
            resolved_commit_sha=resolved_commit_sha,
            manifest_digest_sha256=manifest_digest_sha256,
            source_ref=ref_value,
            trust_profile=policy.trust_profile,
            installed_at_utc=utc_now_iso(),
            security_mode=policy.security_mode,
            security_profile=policy.security_profile,
            security_policy_version=policy.security_policy_version,
            compat_fallbacks=policy.compat_fallbacks,
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
        self._verify_extension_integrity(extension)
        control_plane_workload_record = self._resolve_control_plane_workload_record(
            extension=extension,
            workload=workload_record,
        )

        if workload_record.contract_style == CONTRACT_STYLE_SDK_V0 or extension.contract_style == CONTRACT_STYLE_SDK_V0:
            return await self._run_sdk_workload(
                extension=extension,
                workload=workload_record,
                control_plane_workload_record=control_plane_workload_record,
                input_config=input_config,
                workspace=workspace,
                department=department,
                interaction_context=interaction_context,
            )
        return await self._run_legacy_workload(
            extension=extension,
            workload=workload_record,
            control_plane_workload_record=control_plane_workload_record,
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

    @staticmethod
    def _resolve_commit_sha(repo_path: Path, ref: str) -> str:
        target_ref = str(ref or "").strip() or "HEAD"
        result = subprocess.run(
            ["git", "rev-parse", f"{target_ref}^{{commit}}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"E_EXT_REF_RESOLVE_FAILED: {target_ref}")
        return result.stdout.strip()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()

    def _verify_extension_integrity(self, extension: ExtensionRecord) -> None:
        extension_path = Path(extension.path).resolve()
        manifest_path_raw = str(extension.manifest_path or "").strip()
        if extension.resolved_commit_sha:
            git_dir = extension_path / ".git"
            if git_dir.exists():
                current = self._resolve_commit_sha(extension_path, "HEAD")
                if current != extension.resolved_commit_sha:
                    raise RuntimeError("E_EXT_COMMIT_MISMATCH")
        if manifest_path_raw and extension.manifest_digest_sha256:
            manifest_path = Path(manifest_path_raw).resolve()
            current_digest = self._sha256_file(manifest_path)
            if current_digest != extension.manifest_digest_sha256:
                raise RuntimeError("E_EXT_MANIFEST_DIGEST_MISMATCH")

    @staticmethod
    def _evaluate_source_policy(repo: str) -> _SourcePolicyDecision:
        mode = str(os.getenv("ORKET_EXT_SECURITY_MODE", "compat")).strip().lower() or "compat"
        profile = str(os.getenv("ORKET_EXT_SECURITY_PROFILE", "production")).strip().lower() or "production"
        allowed_hosts_raw = str(
            os.getenv("ORKET_EXT_ALLOWED_HOSTS", "github.com,gitlab.com,gitea.local,localhost")
        ).strip()
        allowed_hosts = {item.strip().lower() for item in allowed_hosts_raw.split(",") if item.strip()}
        allowed_protocols = {"https", "ssh"}
        fallback_codes: list[str] = []

        source_kind, protocol, host = ExtensionManager._classify_repo_source(repo)
        production = profile == "production"
        enforce = mode == "enforce"

        def _deny_or_fallback(code: str, fallback_code: str) -> None:
            if production and enforce:
                raise RuntimeError(code)
            fallback_codes.append(fallback_code)

        if source_kind == "local":
            if production:
                _deny_or_fallback("E_EXT_TRUST_SOURCE_LOCAL_PATH_DENIED", "EXT_LOCAL_PATH_COMPAT")
            else:
                fallback_codes.append("DEV_PROFILE_EXCEPTION_LOCAL_PATH")
        else:
            if protocol and protocol not in allowed_protocols and production:
                _deny_or_fallback("E_EXT_TRUST_PROTOCOL_DENIED", "EXT_PROTOCOL_COMPAT")
            if host and host not in allowed_hosts and production:
                _deny_or_fallback("E_EXT_TRUST_HOST_DENIED", "EXT_HOST_COMPAT")

        return _SourcePolicyDecision(
            security_mode=mode,
            security_profile=profile,
            security_policy_version=hashlib.sha256(
                str(
                    {
                        "mode": mode,
                        "profile": profile,
                        "allowed_hosts": sorted(allowed_hosts),
                        "allowed_protocols": sorted(allowed_protocols),
                    }
                ).encode("utf-8")
            ).hexdigest(),
            trust_profile=profile,
            compat_fallbacks=tuple(sorted(set(fallback_codes))),
        )

    @staticmethod
    def _classify_repo_source(repo: str) -> tuple[str, str, str]:
        value = str(repo or "").strip()
        if not value:
            return ("local", "", "")
        path_candidate = Path(value)
        if path_candidate.exists() or path_candidate.is_absolute() or value.startswith("."):
            return ("local", "file", "localhost")
        if re.match(r"^[^@]+@[^:]+:.+$", value):
            host = value.split("@", 1)[1].split(":", 1)[0].strip().lower()
            return ("remote", "ssh", host)
        parsed = urlparse(value)
        if parsed.scheme:
            protocol = parsed.scheme.strip().lower()
            host = (parsed.hostname or "").strip().lower()
            if protocol == "file":
                return ("local", protocol, host or "localhost")
            return ("remote", protocol, host)
        return ("local", "file", "localhost")


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
