from __future__ import annotations

from collections import Counter
import platform
from typing import Any

from .protocol_hashing import hash_env_allowlist


def resolve_skill_tool_binding(context: dict[str, Any], tool_name: str) -> dict[str, Any] | None:
    bindings = context.get("skill_tool_bindings")
    if not isinstance(bindings, dict):
        return None
    binding = bindings.get(str(tool_name).strip())
    if not isinstance(binding, dict):
        return None
    return binding


def permission_values(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        normalized = values.strip()
        return {normalized} if normalized else set()
    if isinstance(values, list):
        return {str(item).strip() for item in values if str(item).strip()}
    return set()


def missing_required_permissions(binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
    required = binding.get("required_permissions")
    if not isinstance(required, dict) or not required:
        return []
    granted = context.get("granted_permissions")
    granted = granted if isinstance(granted, dict) else {}
    missing: list[str] = []
    for scope, values in required.items():
        required_values = permission_values(values)
        granted_values = permission_values(granted.get(scope))
        for value in sorted(required_values - granted_values):
            missing.append(f"{scope}:{value}")
    return missing


def as_positive_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def runtime_limit_violations(binding: dict[str, Any], context: dict[str, Any]) -> list[str]:
    limits = binding.get("runtime_limits")
    if not isinstance(limits, dict) or not limits:
        return []
    violations: list[str] = []
    requested_exec = as_positive_float(limits.get("max_execution_time"))
    requested_memory = as_positive_float(limits.get("max_memory"))
    allowed_exec = as_positive_float(context.get("max_tool_execution_time"))
    allowed_memory = as_positive_float(context.get("max_tool_memory"))
    if requested_exec is not None and allowed_exec is not None and requested_exec > allowed_exec:
        violations.append("max_execution_time")
    if requested_memory is not None and allowed_memory is not None and requested_memory > allowed_memory:
        violations.append("max_memory")
    return violations


def required_tools(context: dict[str, Any]) -> list[str]:
    required = [
        str(tool).strip()
        for tool in (context.get("required_action_tools") or [])
        if str(tool).strip()
    ]
    deduped: list[str] = []
    for tool in required:
        if tool not in deduped:
            deduped.append(tool)
    return deduped


def required_sequence(context: dict[str, Any]) -> list[str]:
    sequence = context.get("required_sequence")
    if sequence is None:
        sequence = context.get("required_tool_sequence")
    values = [str(tool).strip() for tool in (sequence or []) if str(tool).strip()]
    deduped: list[str] = []
    for tool in values:
        if tool not in deduped:
            deduped.append(tool)
    return deduped


def required_tools_violation(*, observed_tool_names: list[str], context: dict[str, Any]) -> str | None:
    required = required_tools(context)
    if not required:
        return None
    counts = Counter(observed_tool_names)
    for tool_name in required:
        count = int(counts.get(tool_name, 0))
        if count == 0:
            return f"E_MISSING_REQUIRED_TOOL:{tool_name}"
        if count != 1:
            return f"E_TOOL_CARDINALITY:{tool_name}:{count}"
    return None


def required_sequence_violation(*, observed_tool_names: list[str], context: dict[str, Any]) -> str | None:
    sequence = required_sequence(context)
    if not sequence:
        return None
    sequence_set = set(sequence)
    filtered = [tool_name for tool_name in observed_tool_names if tool_name in sequence_set]
    if filtered != sequence:
        return "E_TOOL_SEQUENCE"
    return None


def build_execution_capsule(context: dict[str, Any]) -> dict[str, Any]:
    env_allowlist = context.get("env_allowlist")
    if not isinstance(env_allowlist, dict):
        env_allowlist = {}
    toolchain = context.get("toolchain_version_set")
    if not isinstance(toolchain, dict):
        toolchain = {}
    return {
        "executor_image_digest": str(context.get("executor_image_digest") or ""),
        "toolchain_version_set": dict(toolchain),
        "os_arch": str(context.get("os_arch") or platform.machine() or "unknown"),
        "network_mode": str(context.get("network_mode") or "off"),
        "clock_mode": str(context.get("clock_mode") or "wall"),
        "timezone": str(context.get("timezone") or "UTC"),
        "locale": str(context.get("locale") or "C.UTF-8"),
        "env_allowlist_hash": hash_env_allowlist(env_allowlist),
    }
