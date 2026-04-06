from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from orket.core.domain import CapabilityClass


def run_id_for(*, session_id: str, issue_id: str, role_name: str, turn_index: int) -> str:
    role_token = str(role_name or "").strip().lower().replace(" ", "_") or "unknown-role"
    return f"turn-tool-run:{session_id}:{issue_id}:{role_token}:{int(turn_index):04d}"


def attempt_id_for(*, run_id: str, ordinal: int = 1) -> str:
    return f"{run_id}:attempt:{int(ordinal):04d}"


def effect_id_for(*, operation_id: str) -> str:
    return f"turn-tool-effect:{operation_id}"


def preflight_result_ref(*, run_id: str, violation_reasons: list[str]) -> str:
    reason_token = hashlib.sha256("|".join(sorted(violation_reasons)).encode("utf-8")).hexdigest()[:12]
    return f"turn-tool-preflight:{run_id}:{reason_token}"


def tool_call_ref(*, tool_call_digest: str) -> str:
    return f"turn-tool-call:{tool_call_digest}"


def tool_result_ref(*, operation_id: str) -> str:
    return f"turn-tool-result:{operation_id}"


def tool_operation_ref(*, operation_id: str) -> str:
    return f"turn-tool-operation:{operation_id}"


def tool_authorization_ref(*, tool_call_digest: str) -> str:
    return f"turn-tool-authorization:{tool_call_digest}"


def step_result_classification(*, result: dict[str, Any], replayed: bool) -> str:
    if replayed:
        return "replayed_result"
    return "tool_succeeded" if bool(result.get("ok", False)) else "tool_failed"


def run_namespace_scope(*, issue_id: str, context: dict[str, Any] | None = None) -> str:
    payload = dict(context or {})
    explicit = str(payload.get("run_namespace_scope") or payload.get("namespace_scope") or "").strip()
    if explicit:
        return explicit
    issue_token = str(issue_id or "").strip()
    return f"issue:{issue_token or 'unknown-issue'}"


def capability_for(*, tool_name: str, binding: dict[str, Any] | None) -> CapabilityClass:
    capability_profile = str((binding or {}).get("capability_profile") or "workspace").strip().lower()
    normalized_tool = str(tool_name or "").strip().lower()
    if normalized_tool.startswith(("read", "list", "search", "get")):
        return CapabilityClass.OBSERVE
    if capability_profile == "external":
        return CapabilityClass.EXTERNAL_MUTATION
    if normalized_tool.startswith(("delete", "remove", "kill", "drop", "archive")):
        return CapabilityClass.DESTRUCTIVE_MUTATION
    if str((binding or {}).get("determinism_class") or "").strip().lower() == "pure":
        return CapabilityClass.DETERMINISTIC_COMPUTE
    return CapabilityClass.BOUNDED_LOCAL_MUTATION


def _workspace_ref(token: str) -> str:
    return f"workspace:{token.replace(chr(92), '/')}"


def resource_refs(
    *,
    tool_name: str,
    tool_args: dict[str, Any],
    result: dict[str, Any],
    namespace_scope: str | None = None,
) -> list[str]:
    refs = [f"tool:{str(tool_name or '').strip()}"]
    for key in ("path", "target_path", "workspace_path"):
        token = str(tool_args.get(key) or "").strip()
        if token:
            refs.append(_workspace_ref(token))
    paths = tool_args.get("paths")
    if isinstance(paths, list):
        for raw in paths:
            token = str(raw or "").strip()
            if token:
                refs.append(_workspace_ref(token))
    touched = result.get("touched_paths")
    if isinstance(touched, list):
        for raw in touched:
            token = str(raw or "").strip()
            if token:
                refs.append(_workspace_ref(token))
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    namespace_token = str(namespace_scope or "").strip()
    if namespace_token:
        namespace_ref = f"namespace:{namespace_token}"
        if namespace_ref not in deduped:
            deduped.append(namespace_ref)
    return deduped


def digest(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "attempt_id_for",
    "capability_for",
    "digest",
    "effect_id_for",
    "preflight_result_ref",
    "resource_refs",
    "run_id_for",
    "run_namespace_scope",
    "step_result_classification",
    "tool_authorization_ref",
    "tool_call_ref",
    "tool_operation_ref",
    "tool_result_ref",
    "utc_now",
]
