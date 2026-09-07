from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Protocol

from orket.application.services.governed_agent_admission import validate_governed_agent_host_features
from orket_extension_sdk.manifest import ExtensionManifest

from .models import ExtensionRecord, GovernedAgentWorkloadLaunch, LoadedManifest, _ExtensionManifestEntry


class _AgentCatalogOwner(Protocol):
    def _resolve_manifest_entry(
        self,
        workload_id: str,
    ) -> tuple[ExtensionRecord, _ExtensionManifestEntry] | None: ...

    def _verify_extension_integrity(self, extension: ExtensionRecord) -> None: ...

    def _load_manifest(self, extension_root: Path) -> LoadedManifest: ...

    def _resolve_control_plane_workload_record(
        self,
        *,
        extension: ExtensionRecord,
        workload: _ExtensionManifestEntry,
    ) -> dict[str, Any]: ...


def resolve_governed_agent_catalog_entry(
    owner: _AgentCatalogOwner,
    workload_id: str,
) -> GovernedAgentWorkloadLaunch:
    resolved = owner._resolve_manifest_entry(workload_id)
    if resolved is None:
        raise ValueError(f"Unknown workload '{workload_id}'")
    extension, workload = resolved
    owner._verify_extension_integrity(extension)
    if workload.workload_kind != "agent" or not workload.agent_declaration:
        raise ValueError("E_AGENT_WORKLOAD_KIND_REQUIRED")
    loaded = owner._load_manifest(Path(extension.path))
    manifest = ExtensionManifest.model_validate(loaded.payload)
    validate_governed_agent_host_features(manifest)
    extension_digest = "sha256:" + hashlib.sha256(
        f"{extension.extension_id}:{extension.extension_version}:{extension.manifest_digest_sha256}".encode()
    ).hexdigest()
    return GovernedAgentWorkloadLaunch(
        extension_id=extension.extension_id,
        extension_version=extension.extension_version,
        extension_root=Path(extension.path).resolve(),
        workload_id=workload.workload_id,
        workload_version=workload.workload_version,
        entrypoint=workload.entrypoint,
        allowed_stdlib_modules=extension.allowed_stdlib_modules,
        extension_digest=extension_digest,
        manifest_digest_sha256=extension.manifest_digest_sha256,
        agent_declaration=dict(workload.agent_declaration),
        control_plane_workload_record=owner._resolve_control_plane_workload_record(
            extension=extension,
            workload=workload,
        ),
    )
