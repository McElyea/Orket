from __future__ import annotations

from copy import deepcopy
from typing import Any

SESSION_CONTEXT_VERSION = "packet1_session_context_v1"


def _normalized_required_capabilities(value: Any) -> list[str]:
    normalized: list[str] = []
    for item in list(value or []):
        token = str(item or "").strip()
        if token:
            normalized.append(token)
    return normalized


def build_packet1_context_envelope(
    *,
    session_id: str,
    session_params: dict[str, Any],
    context_inputs: dict[str, Any],
) -> dict[str, Any]:
    normalized_inputs = dict(context_inputs or {})
    required_capabilities = _normalized_required_capabilities(normalized_inputs.get("required_capabilities"))
    envelope = {
        "context_version": SESSION_CONTEXT_VERSION,
        "continuity": {
            "session_id": str(session_id or "").strip(),
            "session_params": deepcopy(dict(session_params or {})),
        },
        "turn_request": {
            "input_config": deepcopy(dict(normalized_inputs.get("input_config") or {})),
            "turn_params": deepcopy(dict(normalized_inputs.get("turn_params") or {})),
            "workload_id": str(normalized_inputs.get("workload_id") or "").strip(),
            "department": str(normalized_inputs.get("department") or "").strip(),
            "workspace": str(normalized_inputs.get("workspace") or "").strip(),
        },
        "extension_manifest": {},
    }
    if required_capabilities:
        envelope["extension_manifest"] = {
            "required_capabilities": required_capabilities,
        }
    return envelope


def build_packet1_provider_lineage(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    extension_manifest = dict(envelope.get("extension_manifest") or {})
    required_capabilities = _normalized_required_capabilities(extension_manifest.get("required_capabilities"))
    return [
        {
            "order": 1,
            "provider_id": "host_continuity",
            "authority": "host_owned",
            "source_surface": "POST /v1/interactions/sessions",
            "fields": ["session_id", "session_params"],
            "present": True,
        },
        {
            "order": 2,
            "provider_id": "turn_request",
            "authority": "host_validated_request",
            "source_surface": "POST /v1/interactions/{session_id}/turns",
            "fields": ["input_config", "turn_params", "workload_id", "department", "workspace"],
            "present": True,
        },
        {
            "order": 3,
            "provider_id": "extension_manifest_required_capabilities",
            "authority": "host_resolved_manifest_metadata",
            "source_surface": "extension_manifest",
            "fields": ["required_capabilities"],
            "present": bool(required_capabilities),
        },
    ]


def flatten_packet1_context(envelope: dict[str, Any]) -> dict[str, Any]:
    continuity = dict(envelope.get("continuity") or {})
    turn_request = dict(envelope.get("turn_request") or {})
    extension_manifest = dict(envelope.get("extension_manifest") or {})
    flattened = {
        "session_params": deepcopy(dict(continuity.get("session_params") or {})),
        "input_config": deepcopy(dict(turn_request.get("input_config") or {})),
        "turn_params": deepcopy(dict(turn_request.get("turn_params") or {})),
        "workload_id": str(turn_request.get("workload_id") or "").strip(),
        "department": str(turn_request.get("department") or "").strip(),
        "workspace": str(turn_request.get("workspace") or "").strip(),
    }
    required_capabilities = _normalized_required_capabilities(extension_manifest.get("required_capabilities"))
    if required_capabilities:
        flattened["required_capabilities"] = required_capabilities
    return flattened
