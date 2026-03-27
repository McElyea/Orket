from __future__ import annotations

import math
from typing import Any

from .protocol_hashing import hash_canonical_json

_RUNTIME_ONLY_METADATA_KEYS = {"trace_id", "debug_flags", "retry_count"}
_VALID_RINGS = {"core", "compatibility", "experimental"}
_VALID_DETERMINISM_CLASSES = {"pure", "workspace", "external"}
_VALID_NAMESPACE_SCOPE_RULES = {"run_scope_only", "declared_scope_subset"}


def normalize_tool_invocation_manifest(
    *,
    manifest: dict[str, Any] | None,
    run_id: str,
    tool_name_fallback: str = "",
) -> dict[str, Any] | None:
    if not isinstance(manifest, dict):
        return None
    candidate = dict(manifest)
    candidate["manifest_version"] = str(candidate.get("manifest_version") or "1.0")
    candidate["tool_name"] = str(candidate.get("tool_name") or tool_name_fallback).strip()
    candidate["ring"] = str(candidate.get("ring") or "core").strip().lower()
    candidate["schema_version"] = str(candidate.get("schema_version") or "1.0.0")
    candidate["determinism_class"] = str(candidate.get("determinism_class") or "workspace").strip().lower()
    candidate["capability_profile"] = str(candidate.get("capability_profile") or "workspace")
    candidate["tool_contract_version"] = str(candidate.get("tool_contract_version") or "1.0.0")
    candidate["run_id"] = str(candidate.get("run_id") or run_id).strip()
    candidate["namespace_scope"] = str(candidate.get("namespace_scope") or "").strip()
    candidate["namespace_scope_rule"] = str(candidate.get("namespace_scope_rule") or "run_scope_only").strip().lower()
    candidate["declared_namespace_scopes"] = [
        str(token).strip() for token in list(candidate.get("declared_namespace_scopes") or []) if str(token).strip()
    ]
    for field in (
        "control_plane_run_id",
        "control_plane_attempt_id",
        "control_plane_reservation_id",
        "control_plane_lease_id",
        "control_plane_resource_id",
    ):
        token = str(candidate.get(field) or "").strip()
        if token:
            candidate[field] = token
        else:
            candidate.pop(field, None)

    if not candidate["tool_name"]:
        return None
    if candidate["run_id"] != str(run_id).strip():
        return None
    if candidate["ring"] not in _VALID_RINGS:
        return None
    if candidate["determinism_class"] not in _VALID_DETERMINISM_CLASSES:
        return None
    if candidate["namespace_scope_rule"] not in _VALID_NAMESPACE_SCOPE_RULES:
        return None

    digest_payload = dict(candidate)
    digest_payload.pop("manifest_hash", None)
    candidate["manifest_hash"] = hash_canonical_json(digest_payload)
    return candidate


def build_tool_invocation_manifest(
    *,
    run_id: str,
    tool_name: str,
    ring: str = "core",
    schema_version: str = "1.0.0",
    determinism_class: str = "workspace",
    capability_profile: str = "workspace",
    tool_contract_version: str = "1.0.0",
    manifest_version: str = "1.0",
    namespace_scope: str = "",
    namespace_scope_rule: str = "run_scope_only",
    declared_namespace_scopes: list[str] | None = None,
    control_plane_run_id: str | None = None,
    control_plane_attempt_id: str | None = None,
    control_plane_reservation_id: str | None = None,
    control_plane_lease_id: str | None = None,
    control_plane_resource_id: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_tool_invocation_manifest(
        manifest={
            "manifest_version": str(manifest_version),
            "tool_name": str(tool_name),
            "ring": str(ring),
            "schema_version": str(schema_version),
            "determinism_class": str(determinism_class),
            "capability_profile": str(capability_profile),
            "tool_contract_version": str(tool_contract_version),
            "run_id": str(run_id),
            "namespace_scope": str(namespace_scope),
            "namespace_scope_rule": str(namespace_scope_rule),
            "declared_namespace_scopes": list(declared_namespace_scopes or []),
            "control_plane_run_id": None if control_plane_run_id is None else str(control_plane_run_id),
            "control_plane_attempt_id": None
            if control_plane_attempt_id is None
            else str(control_plane_attempt_id),
            "control_plane_reservation_id": None
            if control_plane_reservation_id is None
            else str(control_plane_reservation_id),
            "control_plane_lease_id": None if control_plane_lease_id is None else str(control_plane_lease_id),
            "control_plane_resource_id": None
            if control_plane_resource_id is None
            else str(control_plane_resource_id),
        },
        run_id=str(run_id),
        tool_name_fallback=str(tool_name),
    )
    if normalized is None:
        raise ValueError("E_TOOL_INVOCATION_MANIFEST_INVALID")
    return normalized


def normalize_tool_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}
    normalized = _normalize_value(args)
    if isinstance(normalized, dict):
        return normalized
    return {}


def compute_tool_call_hash(
    *,
    tool_name: str,
    tool_args: Any,
    tool_contract_version: str,
    capability_profile: str,
) -> str:
    normalized_args = normalize_tool_args(tool_args)
    return hash_canonical_json(
        {
            "tool_name": str(tool_name or "").strip(),
            "normalized_args": normalized_args,
            "tool_contract_version": str(tool_contract_version or "").strip(),
            "capability_profile": str(capability_profile or "").strip(),
        }
    )


def _normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key in _RUNTIME_ONLY_METADATA_KEYS:
                continue
            normalized[key] = _normalize_value(raw_value)
        return normalized
    return str(value)
