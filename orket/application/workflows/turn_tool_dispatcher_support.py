from __future__ import annotations

from collections import Counter
import platform
from typing import Any

from orket.runtime.protocol_error_codes import (
    E_CAPABILITY_VIOLATION_PREFIX,
    E_DETERMINISM_POLICY_VIOLATION_PREFIX,
    E_DETERMINISM_VIOLATION_PREFIX,
    E_MISSING_REQUIRED_TOOL_PREFIX,
    E_RING_POLICY_VIOLATION_PREFIX,
    E_TOOL_CARDINALITY_PREFIX,
    E_TOOL_INVOCATION_BOUNDARY_PREFIX,
    E_TOOL_SEQUENCE,
    format_protocol_error,
)

from .protocol_hashing import hash_clock_artifact_ref, hash_env_allowlist, hash_network_allowlist

_VALID_TOOL_RINGS = {"core", "compatibility", "experimental"}
_VALID_DETERMINISM_CLASSES = {"pure", "workspace", "external"}
_DETERMINISM_RANK = {"pure": 0, "workspace": 1, "external": 2}


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
            return format_protocol_error(E_MISSING_REQUIRED_TOOL_PREFIX, tool_name)
        if count != 1:
            return format_protocol_error(E_TOOL_CARDINALITY_PREFIX, f"{tool_name}:{count}")
    return None


def required_sequence_violation(*, observed_tool_names: list[str], context: dict[str, Any]) -> str | None:
    sequence = required_sequence(context)
    if not sequence:
        return None
    sequence_set = set(sequence)
    filtered = [tool_name for tool_name in observed_tool_names if tool_name in sequence_set]
    if filtered != sequence:
        return E_TOOL_SEQUENCE
    return None


def tool_policy_violation(
    *,
    tool_name: str,
    binding: dict[str, Any] | None,
    context: dict[str, Any],
) -> str | None:
    if bool(context.get("invoked_from_tool")):
        return format_protocol_error(E_TOOL_INVOCATION_BOUNDARY_PREFIX, tool_name)

    policy_binding = dict(binding or {})
    ring = str(policy_binding.get("ring") or "core").strip().lower()
    if ring not in _VALID_TOOL_RINGS:
        return format_protocol_error(E_RING_POLICY_VIOLATION_PREFIX, f"{tool_name}:ring={ring}")

    allowed_rings = _normalized_tokens(context.get("allowed_tool_rings"))
    if not allowed_rings:
        allowed_rings = {"core"}
    if ring not in allowed_rings:
        allowed = ",".join(sorted(allowed_rings))
        return format_protocol_error(E_RING_POLICY_VIOLATION_PREFIX, f"{tool_name}:ring={ring}:allowed={allowed}")

    capability_profile = str(policy_binding.get("capability_profile") or "workspace").strip().lower()
    allowed_capabilities = _normalized_tokens(context.get("capabilities_allowed"))
    if not allowed_capabilities:
        allowed_capabilities = _normalized_tokens(context.get("allowed_capability_profiles"))
    if not allowed_capabilities:
        allowed_capabilities = {"workspace"}
    if capability_profile not in allowed_capabilities:
        allowed = ",".join(sorted(allowed_capabilities))
        return format_protocol_error(
            E_CAPABILITY_VIOLATION_PREFIX,
            f"{tool_name}:capability={capability_profile}:allowed={allowed}",
        )

    determinism_class = str(policy_binding.get("determinism_class") or "workspace").strip().lower()
    if determinism_class not in _VALID_DETERMINISM_CLASSES:
        return format_protocol_error(
            E_DETERMINISM_POLICY_VIOLATION_PREFIX,
            f"{tool_name}:determinism_class={determinism_class}",
        )

    run_determinism_class = str(
        context.get("run_determinism_class") or context.get("run_determinism_policy") or "workspace"
    ).strip().lower()
    if run_determinism_class not in _VALID_DETERMINISM_CLASSES:
        run_determinism_class = "workspace"
    if _DETERMINISM_RANK[determinism_class] > _DETERMINISM_RANK[run_determinism_class]:
        return format_protocol_error(
            E_DETERMINISM_POLICY_VIOLATION_PREFIX,
            f"{tool_name}:{determinism_class}>{run_determinism_class}",
        )
    return None


def determinism_violation_for_result(
    *,
    tool_name: str,
    binding: dict[str, Any] | None,
    result: dict[str, Any] | None,
) -> str | None:
    determinism_class = str((binding or {}).get("determinism_class") or "workspace").strip().lower()
    if determinism_class != "pure":
        return None

    side_effect_signals = False
    pure_conflict_tools = {
        "write_file",
        "delete_file",
        "create_issue",
        "update_issue_status",
        "add_issue_comment",
    }
    if str(tool_name).strip() in pure_conflict_tools:
        side_effect_signals = True

    payload = result if isinstance(result, dict) else {}
    for key in (
        "side_effects",
        "side_effect",
        "writes",
        "mutations",
        "touched_paths",
        "changed_files",
        "external_calls",
    ):
        value = payload.get(key)
        if value:
            side_effect_signals = True
            break

    if not side_effect_signals:
        return None
    return format_protocol_error(E_DETERMINISM_VIOLATION_PREFIX, f"{tool_name}:declared_pure")


def _normalized_tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {token.strip().lower() for token in value.split(",") if token.strip()}
    if isinstance(value, list):
        return {str(token).strip().lower() for token in value if str(token).strip()}
    if isinstance(value, tuple):
        return {str(token).strip().lower() for token in value if str(token).strip()}
    if isinstance(value, set):
        return {str(token).strip().lower() for token in value if str(token).strip()}
    return set()


def build_execution_capsule(context: dict[str, Any]) -> dict[str, Any]:
    env_allowlist = context.get("env_allowlist")
    if not isinstance(env_allowlist, dict):
        env_allowlist = {}
    network_allowlist_values = context.get("network_allowlist_values")
    if not isinstance(network_allowlist_values, list):
        network_allowlist_values = []
    clock_artifact_ref = str(context.get("clock_artifact_ref") or "")
    toolchain = context.get("toolchain_version_set")
    if not isinstance(toolchain, dict):
        toolchain = {}
    env_allowlist_hash = str(context.get("env_allowlist_hash") or hash_env_allowlist(env_allowlist))
    network_allowlist_hash = str(
        context.get("network_allowlist_hash") or hash_network_allowlist(network_allowlist_values)
    )
    clock_artifact_hash = str(context.get("clock_artifact_hash") or hash_clock_artifact_ref(clock_artifact_ref))
    return {
        "executor_image_digest": str(context.get("executor_image_digest") or ""),
        "toolchain_version_set": dict(toolchain),
        "os_arch": str(context.get("os_arch") or platform.machine() or "unknown"),
        "network_mode": str(context.get("network_mode") or "off"),
        "network_allowlist_hash": network_allowlist_hash,
        "clock_mode": str(context.get("clock_mode") or "wall"),
        "clock_artifact_ref": clock_artifact_ref,
        "clock_artifact_hash": clock_artifact_hash,
        "timezone": str(context.get("timezone") or "UTC"),
        "locale": str(context.get("locale") or "C.UTF-8"),
        "env_allowlist_hash": env_allowlist_hash,
    }
