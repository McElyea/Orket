from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket_extension_sdk.manifest import load_manifest as load_sdk_manifest

from .models import (
    CONTRACT_STYLE_LEGACY,
    CONTRACT_STYLE_SDK_V0,
    LEGACY_MANIFEST_FILENAME,
    SDK_MANIFEST_FILENAMES,
    ExtensionRecord,
    LoadedManifest,
    _ExtensionManifestEntry,
)


class ManifestParser:
    """Manifest loading and conversion into extension catalog records."""

    def load_manifest(self, repo_path: Path) -> LoadedManifest:
        legacy_manifest_path = repo_path / LEGACY_MANIFEST_FILENAME
        if legacy_manifest_path.exists():
            manifest = json.loads(legacy_manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError(f"{LEGACY_MANIFEST_FILENAME} must be a JSON object")
            return LoadedManifest(
                payload=manifest,
                manifest_path=legacy_manifest_path,
                contract_style=CONTRACT_STYLE_LEGACY,
            )

        for filename in SDK_MANIFEST_FILENAMES:
            sdk_manifest_path = repo_path / filename
            if not sdk_manifest_path.exists():
                continue
            manifest_model = load_sdk_manifest(sdk_manifest_path)
            return LoadedManifest(
                payload=manifest_model.model_dump(mode="json"),
                manifest_path=sdk_manifest_path,
                contract_style=CONTRACT_STYLE_SDK_V0,
            )

        expected = [LEGACY_MANIFEST_FILENAME, *SDK_MANIFEST_FILENAMES]
        raise FileNotFoundError(f"Missing extension manifest in repo: {repo_path} (expected one of {expected})")

    def record_from_manifest(
        self,
        manifest: dict[str, Any],
        *,
        source: str,
        path: Path,
        contract_style: str,
        manifest_path: Path,
        resolved_commit_sha: str = "",
        manifest_digest_sha256: str = "",
        source_ref: str = "",
        trust_profile: str = "compat",
        installed_at_utc: str = "",
        security_mode: str = "compat",
        security_profile: str = "production",
        security_policy_version: str = "",
        compat_fallbacks: tuple[str, ...] = (),
    ) -> ExtensionRecord:
        if contract_style == CONTRACT_STYLE_SDK_V0:
            return self.sdk_record_from_manifest(
                manifest,
                source=source,
                path=path,
                manifest_path=manifest_path,
                resolved_commit_sha=resolved_commit_sha,
                manifest_digest_sha256=manifest_digest_sha256,
                source_ref=source_ref,
                trust_profile=trust_profile,
                installed_at_utc=installed_at_utc,
                security_mode=security_mode,
                security_profile=security_profile,
                security_policy_version=security_policy_version,
                compat_fallbacks=compat_fallbacks,
            )
        return self.legacy_record_from_manifest(
            manifest,
            source=source,
            path=path,
            manifest_path=manifest_path,
            resolved_commit_sha=resolved_commit_sha,
            manifest_digest_sha256=manifest_digest_sha256,
            source_ref=source_ref,
            trust_profile=trust_profile,
            installed_at_utc=installed_at_utc,
            security_mode=security_mode,
            security_profile=security_profile,
            security_policy_version=security_policy_version,
            compat_fallbacks=compat_fallbacks,
        )

    def legacy_record_from_manifest(
        self,
        manifest: dict[str, Any],
        *,
        source: str,
        path: Path,
        manifest_path: Path,
        resolved_commit_sha: str = "",
        manifest_digest_sha256: str = "",
        source_ref: str = "",
        trust_profile: str = "compat",
        installed_at_utc: str = "",
        security_mode: str = "compat",
        security_profile: str = "production",
        security_policy_version: str = "",
        compat_fallbacks: tuple[str, ...] = (),
    ) -> ExtensionRecord:
        extension_id = str(manifest.get("extension_id", "")).strip()
        extension_version = str(manifest.get("extension_version", "")).strip()
        extension_api_version = str(manifest.get("extension_api_version", "")).strip() or "1.0.0"
        module = str(manifest.get("module", "")).strip()
        register_callable = str(manifest.get("register_callable", "")).strip() or "register"
        if not extension_id:
            raise ValueError("extension_id is required in manifest")
        if not extension_version:
            raise ValueError("extension_version is required in manifest")
        if not module:
            raise ValueError("module is required in manifest")

        manifest_entries: list[_ExtensionManifestEntry] = []
        config_sections = tuple(str(item).strip() for item in manifest.get("config_sections", []) if str(item).strip())
        allowed_stdlib_modules = tuple(
            str(item).strip() for item in manifest.get("allowed_stdlib_modules", []) if str(item).strip()
        )
        for item in manifest.get("workloads", []):
            workload_id = str(item.get("workload_id", "")).strip()
            workload_version = str(item.get("workload_version", "")).strip() or "0.0.0"
            if workload_id:
                manifest_entries.append(
                    _ExtensionManifestEntry(
                        workload_id=workload_id,
                        workload_version=workload_version,
                        contract_style=CONTRACT_STYLE_LEGACY,
                    )
                )

        return ExtensionRecord(
            extension_id=extension_id,
            extension_version=extension_version,
            source=source,
            extension_api_version=extension_api_version,
            path=str(path),
            module=module,
            register_callable=register_callable,
            manifest_entries=tuple(manifest_entries),
            contract_style=CONTRACT_STYLE_LEGACY,
            manifest_path=str(manifest_path),
            resolved_commit_sha=resolved_commit_sha,
            manifest_digest_sha256=manifest_digest_sha256,
            source_ref=source_ref,
            trust_profile=trust_profile,
            installed_at_utc=installed_at_utc,
            security_mode=security_mode,
            security_profile=security_profile,
            security_policy_version=security_policy_version,
            compat_fallbacks=compat_fallbacks,
            config_sections=config_sections,
            allowed_stdlib_modules=allowed_stdlib_modules,
        )

    def sdk_record_from_manifest(
        self,
        manifest: dict[str, Any],
        *,
        source: str,
        path: Path,
        manifest_path: Path,
        resolved_commit_sha: str = "",
        manifest_digest_sha256: str = "",
        source_ref: str = "",
        trust_profile: str = "compat",
        installed_at_utc: str = "",
        security_mode: str = "compat",
        security_profile: str = "production",
        security_policy_version: str = "",
        compat_fallbacks: tuple[str, ...] = (),
    ) -> ExtensionRecord:
        extension_id = str(manifest.get("extension_id", "")).strip()
        extension_version = str(manifest.get("extension_version", "")).strip()
        manifest_version = str(manifest.get("manifest_version", "")).strip() or "v0"
        if not extension_id:
            raise ValueError("extension_id is required in manifest")
        if not extension_version:
            raise ValueError("extension_version is required in manifest")

        manifest_entries: list[_ExtensionManifestEntry] = []
        config_sections = tuple(str(item).strip() for item in manifest.get("config_sections", []) if str(item).strip())
        allowed_stdlib_modules = tuple(
            str(item).strip() for item in manifest.get("allowed_stdlib_modules", []) if str(item).strip()
        )
        for item in manifest.get("workloads", []):
            workload_id = str(item.get("workload_id", "")).strip()
            if not workload_id:
                continue
            required_capabilities = tuple(
                str(cap).strip() for cap in item.get("required_capabilities", []) if str(cap).strip()
            )
            manifest_entries.append(
                _ExtensionManifestEntry(
                    workload_id=workload_id,
                    workload_version=extension_version,
                    entrypoint=str(item.get("entrypoint", "")).strip(),
                    required_capabilities=required_capabilities,
                    contract_style=CONTRACT_STYLE_SDK_V0,
                )
            )

        return ExtensionRecord(
            extension_id=extension_id,
            extension_version=extension_version,
            source=source,
            extension_api_version=manifest_version,
            path=str(path),
            module="",
            register_callable="",
            manifest_entries=tuple(manifest_entries),
            contract_style=CONTRACT_STYLE_SDK_V0,
            manifest_path=str(manifest_path),
            resolved_commit_sha=resolved_commit_sha,
            manifest_digest_sha256=manifest_digest_sha256,
            source_ref=source_ref,
            trust_profile=trust_profile,
            installed_at_utc=installed_at_utc,
            security_mode=security_mode,
            security_profile=security_profile,
            security_policy_version=security_policy_version,
            compat_fallbacks=compat_fallbacks,
            config_sections=config_sections,
            allowed_stdlib_modules=allowed_stdlib_modules,
        )
