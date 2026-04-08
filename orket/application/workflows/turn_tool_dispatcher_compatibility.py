from __future__ import annotations

from typing import Any

from orket.runtime.protocol_error_codes import (
    E_COMPAT_MAPPING_MISSING_PREFIX,
    E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
    format_protocol_error,
)

from orket.runtime.registry.protocol_hashing import hash_canonical_json
from orket.runtime.registry.tool_invocation_contracts import normalize_tool_args

_VALID_DETERMINISM_CLASSES = {"pure", "workspace", "external"}
_DETERMINISM_RANK = {"pure": 0, "workspace": 1, "external": 2}


def resolve_compatibility_translation(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    binding: dict[str, Any] | None,
    context: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    ring = str((binding or {}).get("ring") or "core").strip().lower()
    if ring != "compatibility":
        return None, None

    mappings = context.get("compatibility_mappings")
    if not isinstance(mappings, dict):
        return None, format_protocol_error(E_COMPAT_MAPPING_MISSING_PREFIX, f"{tool_name}:mapping_table")

    mapping = mappings.get(tool_name)
    if not isinstance(mapping, dict):
        return None, format_protocol_error(E_COMPAT_MAPPING_MISSING_PREFIX, tool_name)

    mapping_version = mapping.get("mapping_version")
    if not isinstance(mapping_version, int) or mapping_version <= 0:
        return None, format_protocol_error(E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX, f"{tool_name}:mapping_version")

    mapped_core_tools = _non_empty_string_list(mapping.get("mapped_core_tools"))
    if not mapped_core_tools:
        return None, format_protocol_error(E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX, f"{tool_name}:mapped_core_tools")

    schema_compatibility_range = str(mapping.get("schema_compatibility_range") or "").strip()
    if not schema_compatibility_range:
        return None, format_protocol_error(
            E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
            f"{tool_name}:schema_compatibility_range",
        )

    mapping_determinism = str(mapping.get("determinism_class") or "").strip().lower()
    if mapping_determinism not in _VALID_DETERMINISM_CLASSES:
        return None, format_protocol_error(E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX, f"{tool_name}:determinism_class")

    skill_tool_bindings = context.get("skill_tool_bindings")
    skill_tool_bindings = skill_tool_bindings if isinstance(skill_tool_bindings, dict) else {}
    mapped_determinism: list[str] = []
    translated_calls: list[dict[str, Any]] = []
    normalized_args = normalize_tool_args(tool_args)

    for mapped_tool in mapped_core_tools:
        if mapped_tool in mappings:
            return None, format_protocol_error(
                E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
                f"{tool_name}:compat_chain:{mapped_tool}",
            )
        mapped_binding = skill_tool_bindings.get(mapped_tool)
        if not isinstance(mapped_binding, dict):
            return None, format_protocol_error(
                E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
                f"{tool_name}:missing_binding:{mapped_tool}",
            )
        mapped_ring = str(mapped_binding.get("ring") or "core").strip().lower()
        if mapped_ring != "core":
            return None, format_protocol_error(
                E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
                f"{tool_name}:mapped_ring:{mapped_tool}:{mapped_ring}",
            )
        mapped_determinism_class = str(mapped_binding.get("determinism_class") or "workspace").strip().lower()
        if mapped_determinism_class not in _VALID_DETERMINISM_CLASSES:
            return None, format_protocol_error(
                E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
                f"{tool_name}:mapped_determinism:{mapped_tool}",
            )
        mapped_determinism.append(mapped_determinism_class)
        translated_calls.append(
            {
                "tool_name": mapped_tool,
                "tool_args": dict(normalized_args),
                "binding": dict(mapped_binding),
            }
        )

    least_deterministic = _least_deterministic(mapped_determinism)
    if mapping_determinism != least_deterministic:
        return None, format_protocol_error(
            E_COMPAT_MAPPING_POLICY_VIOLATION_PREFIX,
            f"{tool_name}:determinism:{mapping_determinism}!={least_deterministic}",
        )

    artifact = {
        "compat_tool_name": tool_name,
        "mapping_version": mapping_version,
        "mapping_determinism": mapping_determinism,
        "schema_compatibility_range": schema_compatibility_range,
        "mapped_core_tools": list(mapped_core_tools),
        "translation_hash": hash_canonical_json(
            {
                "compat_tool_name": tool_name,
                "normalized_args": dict(normalized_args),
                "mapping_version": mapping_version,
                "mapped_core_tools": list(mapped_core_tools),
            }
        ),
    }
    return {
        "artifact": artifact,
        "translated_calls": translated_calls,
    }, None


def _non_empty_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        token = str(item or "").strip()
        if not token:
            continue
        if token in rows:
            continue
        rows.append(token)
    return rows


def _least_deterministic(classes: list[str]) -> str:
    resolved = [value for value in classes if value in _DETERMINISM_RANK]
    if not resolved:
        return "pure"
    return max(resolved, key=lambda value: _DETERMINISM_RANK[value])
