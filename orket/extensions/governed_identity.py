from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

EXTENSION_WORKLOAD_CLAIM_TIER = "non_deterministic_lab_only"
EXTENSION_WORKLOAD_COMPARE_SCOPE = "extension_workload_provenance_family_v1"
EXTENSION_WORKLOAD_DETERMINISM_CLASS = "workspace"
EXTENSION_WORKLOAD_POLICY_SURFACE_VERSION = "extension_workload_governed_identity.v1"
EXTENSION_WORKLOAD_OPERATOR_SURFACE_MANIFEST = "extension_artifact_manifest_v1"
EXTENSION_WORKLOAD_OPERATOR_SURFACE_PROVENANCE = "extension_provenance_v1"
EXTENSION_WORKLOAD_OPERATOR_SURFACE_RESULT = "extension_run_result_identity_v1"

_REQUIRED_GOVERNED_FIELDS = (
    "claim_tier",
    "compare_scope",
    "operator_surface",
    "policy_digest",
    "control_bundle_hash",
    "determinism_class",
)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def digest_prefixed(payload: Any) -> str:
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = _canonical_json_bytes(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def build_extension_policy_payload(
    *,
    contract_style: str,
    security_mode: str,
    security_profile: str,
    security_policy_version: str,
    reliable_mode_enabled: bool,
    reliable_require_clean_git: bool,
    provenance_verbose_enabled: bool,
    artifact_file_size_cap_bytes: int,
    artifact_total_size_cap_bytes: int,
) -> dict[str, Any]:
    return {
        "policy_surface_version": EXTENSION_WORKLOAD_POLICY_SURFACE_VERSION,
        "contract_style": str(contract_style or "").strip(),
        "security_mode": str(security_mode or "").strip(),
        "security_profile": str(security_profile or "").strip(),
        "security_policy_version": str(security_policy_version or "").strip(),
        "reliable_mode_enabled": bool(reliable_mode_enabled),
        "reliable_require_clean_git": bool(reliable_require_clean_git),
        "provenance_verbose_enabled": bool(provenance_verbose_enabled),
        "artifact_file_size_cap_bytes": int(artifact_file_size_cap_bytes),
        "artifact_total_size_cap_bytes": int(artifact_total_size_cap_bytes),
    }


def build_extension_control_bundle(
    *,
    extension_id: str,
    extension_version: str,
    source_ref: str,
    resolved_commit_sha: str,
    manifest_digest_sha256: str,
    workload_id: str,
    workload_version: str,
    workload_entrypoint: str,
    required_capabilities: list[str],
    contract_style: str,
    department: str,
    input_identity: str,
    security_mode: str,
    security_profile: str,
    security_policy_version: str,
    reliable_mode_enabled: bool,
) -> dict[str, Any]:
    return {
        "extension_id": str(extension_id or "").strip(),
        "extension_version": str(extension_version or "").strip(),
        "source_ref": str(source_ref or "").strip(),
        "resolved_commit_sha": str(resolved_commit_sha or "").strip(),
        "manifest_digest_sha256": str(manifest_digest_sha256 or "").strip(),
        "workload_id": str(workload_id or "").strip(),
        "workload_version": str(workload_version or "").strip(),
        "workload_entrypoint": str(workload_entrypoint or "").strip(),
        "required_capabilities": list(required_capabilities),
        "contract_style": str(contract_style or "").strip(),
        "department": str(department or "").strip(),
        "input_identity": str(input_identity or "").strip(),
        "security_mode": str(security_mode or "").strip(),
        "security_profile": str(security_profile or "").strip(),
        "security_policy_version": str(security_policy_version or "").strip(),
        "reliable_mode_enabled": bool(reliable_mode_enabled),
    }


def build_governed_identity(
    *,
    operator_surface: str,
    policy_payload: dict[str, Any],
    control_bundle: dict[str, Any],
) -> dict[str, Any]:
    identity = {
        "claim_tier": EXTENSION_WORKLOAD_CLAIM_TIER,
        "compare_scope": EXTENSION_WORKLOAD_COMPARE_SCOPE,
        "operator_surface": str(operator_surface or "").strip(),
        "policy_digest": digest_prefixed(policy_payload),
        "control_bundle_hash": digest_prefixed(control_bundle),
        "determinism_class": EXTENSION_WORKLOAD_DETERMINISM_CLASS,
        "governed_policy": dict(policy_payload),
        "control_bundle": dict(control_bundle),
    }
    validate_governed_identity(identity)
    return identity


def build_extension_governed_identity(
    *,
    extension: Any,
    workload_id: str,
    workload_version: str,
    workload_entrypoint: str,
    required_capabilities: list[str],
    contract_style: str,
    department: str,
    input_identity: str,
    operator_surface: str,
    reliable_mode_enabled: bool,
    reliable_require_clean_git: bool,
    provenance_verbose_enabled: bool,
    artifact_file_size_cap_bytes: int,
    artifact_total_size_cap_bytes: int,
) -> dict[str, Any]:
    policy_payload = build_extension_policy_payload(
        contract_style=contract_style,
        security_mode=extension.security_mode,
        security_profile=extension.security_profile,
        security_policy_version=extension.security_policy_version,
        reliable_mode_enabled=reliable_mode_enabled,
        reliable_require_clean_git=reliable_require_clean_git,
        provenance_verbose_enabled=provenance_verbose_enabled,
        artifact_file_size_cap_bytes=artifact_file_size_cap_bytes,
        artifact_total_size_cap_bytes=artifact_total_size_cap_bytes,
    )
    control_bundle = build_extension_control_bundle(
        extension_id=extension.extension_id,
        extension_version=extension.extension_version,
        source_ref=extension.source_ref,
        resolved_commit_sha=extension.resolved_commit_sha,
        manifest_digest_sha256=extension.manifest_digest_sha256,
        workload_id=workload_id,
        workload_version=workload_version,
        workload_entrypoint=workload_entrypoint,
        required_capabilities=required_capabilities,
        contract_style=contract_style,
        department=department,
        input_identity=input_identity,
        security_mode=extension.security_mode,
        security_profile=extension.security_profile,
        security_policy_version=extension.security_policy_version,
        reliable_mode_enabled=reliable_mode_enabled,
    )
    return build_governed_identity(
        operator_surface=operator_surface,
        policy_payload=policy_payload,
        control_bundle=control_bundle,
    )


def build_base_provenance_payload(
    *,
    extension: Any,
    governed_identity: dict[str, Any],
    artifact_manifest_hash: str,
    artifact_root: str,
    reliable_mode_enabled: bool,
) -> dict[str, Any]:
    return {
        "claim_tier": governed_identity["claim_tier"],
        "compare_scope": governed_identity["compare_scope"],
        "operator_surface": governed_identity["operator_surface"],
        "policy_digest": governed_identity["policy_digest"],
        "control_bundle_hash": governed_identity["control_bundle_hash"],
        "determinism_class": governed_identity["determinism_class"],
        "artifact_manifest_ref": "artifact_manifest.json",
        "artifact_manifest_hash": artifact_manifest_hash,
        "provenance_ref": "provenance.json",
        "governed_policy": governed_identity["governed_policy"],
        "control_bundle": governed_identity["control_bundle"],
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "reliable_mode": bool(reliable_mode_enabled),
        "security": {
            "mode": extension.security_mode,
            "profile": extension.security_profile,
            "policy_version": extension.security_policy_version,
            "compat_fallbacks": list(extension.compat_fallbacks),
            "compat_fallback_count": len(extension.compat_fallbacks),
        },
        "artifact_root": str(artifact_root),
    }


def validate_governed_identity(payload: dict[str, Any]) -> None:
    missing = [field for field in _REQUIRED_GOVERNED_FIELDS if not str(payload.get(field) or "").strip()]
    if missing:
        raise ValueError("E_GOVERNED_IDENTITY_MISSING: " + ",".join(missing))
