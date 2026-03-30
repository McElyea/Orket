from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from orket.runtime_paths import durable_root

RELIABLE_MODE_ENV = "ORKET_RELIABLE_MODE"
RELIABLE_REQUIRE_CLEAN_GIT_ENV = "ORKET_RELIABLE_REQUIRE_CLEAN_GIT"
LEGACY_MANIFEST_FILENAME = "orket_extension.json"
SDK_MANIFEST_FILENAMES = ("extension.yaml", "extension.yml", "extension.json")
CONTRACT_STYLE_LEGACY = "legacy_v1"
CONTRACT_STYLE_SDK_V0 = "sdk_v0"


def default_extensions_catalog_path() -> Path:
    env_path = (os.getenv("ORKET_EXTENSIONS_CATALOG") or "").strip()
    if env_path:
        return Path(env_path)
    return durable_root() / "config" / "extensions_catalog.json"


@dataclass(frozen=True)
class _ExtensionManifestEntry:
    workload_id: str
    workload_version: str
    entrypoint: str = ""
    required_capabilities: tuple[str, ...] = ()
    contract_style: str = CONTRACT_STYLE_LEGACY


@dataclass(frozen=True)
class ExtensionRecord:
    extension_id: str
    extension_version: str
    source: str
    extension_api_version: str
    path: str
    module: str
    register_callable: str
    manifest_entries: tuple[_ExtensionManifestEntry, ...]
    contract_style: str = CONTRACT_STYLE_LEGACY
    manifest_path: str = ""
    resolved_commit_sha: str = ""
    manifest_digest_sha256: str = ""
    source_ref: str = ""
    trust_profile: str = "compat"
    installed_at_utc: str = ""
    security_mode: str = "compat"
    security_profile: str = "production"
    security_policy_version: str = ""
    compat_fallbacks: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtensionRunResult:
    extension_id: str
    extension_version: str
    workload_id: str
    workload_version: str
    plan_hash: str
    artifact_root: str
    provenance_path: str
    summary: dict[str, Any]
    claim_tier: str = ""
    compare_scope: str = ""
    operator_surface: str = ""
    policy_digest: str = ""
    control_bundle_hash: str = ""
    artifact_manifest_path: str = ""
    artifact_manifest_hash: str = ""
    provenance_hash: str = ""
    determinism_class: str = ""
    control_plane_workload_record: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedManifest:
    payload: dict[str, Any]
    manifest_path: Path
    contract_style: str

def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
