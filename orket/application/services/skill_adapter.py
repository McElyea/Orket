from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from orket.application.services.skill_loader import load_skill_manifest_or_raise


def build_tool_profile_bindings(skill_manifest_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Build runtime tool bindings from a validated Skill manifest.

    Binding key is the runtime tool name (`tool_profile_id` in v1 contract).
    """
    loaded = load_skill_manifest_or_raise(skill_manifest_payload)
    manifest = loaded["manifest"]
    bindings: dict[str, dict[str, Any]] = {}
    for entrypoint in manifest.get("entrypoints", []):
        if not isinstance(entrypoint, dict):
            continue
        tool_name = str(entrypoint.get("tool_profile_id") or "").strip()
        if not tool_name:
            continue
        if tool_name in bindings:
            raise ValueError(f"duplicate tool_profile_id binding: {tool_name}")
        bindings[tool_name] = {
            "entrypoint_id": str(entrypoint.get("entrypoint_id") or "").strip() or tool_name,
            "runtime": str(entrypoint.get("runtime") or "").strip() or "unknown",
            "runtime_version": str(entrypoint.get("runtime_version") or "").strip() or "",
            "tool_profile_id": tool_name,
            "tool_profile_version": str(entrypoint.get("tool_profile_version") or "").strip() or "unknown-v1",
            "ring": str(entrypoint.get("ring") or "core").strip().lower() or "core",
            "determinism_class": str(entrypoint.get("determinism_class") or "workspace").strip().lower() or "workspace",
            "capability_profile": str(entrypoint.get("capability_profile") or "workspace").strip().lower()
            or "workspace",
            "tool_contract_version": str(entrypoint.get("tool_contract_version") or "1.0.0").strip() or "1.0.0",
            "runtime_limits": dict(entrypoint.get("runtime_limits") or {}),
            "requested_permissions": dict(entrypoint.get("requested_permissions") or {}),
            "required_permissions": dict(entrypoint.get("required_permissions") or {}),
            "namespace_scope_rule": str(entrypoint.get("namespace_scope_rule") or "run_scope_only").strip().lower()
            or "run_scope_only",
            "declared_namespace_scopes": [
                str(scope).strip()
                for scope in list(entrypoint.get("declared_namespace_scopes") or [])
                if str(scope).strip()
            ],
        }
    return bindings


def synthesize_role_tool_profile_bindings(
    tool_names: Iterable[str],
    *,
    profile_version: str = "role-tools.v1",
) -> dict[str, dict[str, Any]]:
    """
    Build deterministic fallback bindings for role-driven tool execution.
    """
    bindings: dict[str, dict[str, Any]] = {}
    for raw in tool_names:
        tool_name = str(raw or "").strip()
        if not tool_name:
            continue
        if tool_name in bindings:
            continue
        bindings[tool_name] = {
            "entrypoint_id": tool_name,
            "runtime": "role",
            "runtime_version": "",
            "tool_profile_id": tool_name,
            "tool_profile_version": profile_version,
            "ring": "core",
            "determinism_class": "workspace",
            "capability_profile": "workspace",
            "tool_contract_version": "1.0.0",
            "runtime_limits": {},
            "requested_permissions": {},
            "required_permissions": {},
            "namespace_scope_rule": "run_scope_only",
            "declared_namespace_scopes": [],
        }
    return bindings
