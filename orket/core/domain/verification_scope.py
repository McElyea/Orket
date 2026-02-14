from __future__ import annotations

from typing import Any, Dict, Iterable, List


def normalize_scope_values(values: Iterable[object] | None) -> List[str]:
    if values is None:
        return []
    normalized: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return sorted(normalized)


def build_verification_scope(
    *,
    workspace: Iterable[object] | None = None,
    provided_context: Iterable[object] | None = None,
    active_context: Iterable[object] | None = None,
    passive_context: Iterable[object] | None = None,
    archived_context: Iterable[object] | None = None,
    declared_interfaces: Iterable[object] | None = None,
    strict_grounding: bool = False,
    forbidden_phrases: Iterable[object] | None = None,
    enforce_path_hardening: bool = True,
    consistency_tool_calls_only: bool = False,
) -> Dict[str, Any]:
    resolved_active = normalize_scope_values(
        active_context if active_context is not None else provided_context
    )
    return {
        "workspace": normalize_scope_values(workspace),
        "provided_context": list(resolved_active),
        "active_context": list(resolved_active),
        "passive_context": normalize_scope_values(passive_context),
        "archived_context": normalize_scope_values(archived_context),
        "declared_interfaces": normalize_scope_values(declared_interfaces),
        "strict_grounding": bool(strict_grounding),
        "forbidden_phrases": normalize_scope_values(forbidden_phrases),
        "enforce_path_hardening": bool(enforce_path_hardening),
        "consistency_tool_calls_only": bool(consistency_tool_calls_only),
    }


def parse_verification_scope(raw: Any) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return build_verification_scope(
        workspace=raw.get("workspace"),
        provided_context=raw.get("provided_context"),
        active_context=raw.get("active_context"),
        passive_context=raw.get("passive_context"),
        archived_context=raw.get("archived_context"),
        declared_interfaces=raw.get("declared_interfaces"),
        strict_grounding=bool(raw.get("strict_grounding", False)),
        forbidden_phrases=raw.get("forbidden_phrases"),
        enforce_path_hardening=bool(raw.get("enforce_path_hardening", True)),
        consistency_tool_calls_only=bool(raw.get("consistency_tool_calls_only", False)),
    )
