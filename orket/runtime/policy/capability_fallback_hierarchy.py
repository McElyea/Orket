from __future__ import annotations

from typing import Any

from orket.runtime.provider_truth_table import provider_truth_table_snapshot

_FALLBACK_ELIGIBLE_STATES = {"supported", "conditional"}


def _provider_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def capability_fallback_hierarchy_snapshot() -> dict[str, Any]:
    truth_table = provider_truth_table_snapshot()
    providers = _provider_rows(truth_table.get("providers"))
    capability_name_set: set[str] = set()
    for row in providers:
        capabilities_payload = row.get("capabilities")
        if not isinstance(capabilities_payload, dict):
            continue
        for name in capabilities_payload:
            capability = str(name).strip()
            if capability:
                capability_name_set.add(capability)
    capability_names = sorted(capability_name_set)
    hierarchy: dict[str, list[dict[str, str]]] = {}
    for capability in capability_names:
        rows: list[dict[str, str]] = []
        for provider_row in providers:
            provider = str(provider_row.get("provider") or "").strip()
            capabilities = dict(provider_row.get("capabilities") or {})
            state = str(capabilities.get(capability) or "").strip().lower()
            if provider and state in _FALLBACK_ELIGIBLE_STATES:
                rows.append({"provider": provider, "state": state})
        if rows:
            hierarchy[capability] = rows
    return {
        "schema_version": "1.0",
        "eligible_states": sorted(_FALLBACK_ELIGIBLE_STATES),
        "fallback_hierarchy": hierarchy,
    }


def validate_capability_fallback_hierarchy(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    hierarchy = dict(payload or capability_fallback_hierarchy_snapshot())
    fallback_hierarchy_payload = hierarchy.get("fallback_hierarchy")
    fallback_hierarchy = fallback_hierarchy_payload if isinstance(fallback_hierarchy_payload, dict) else {}
    if not fallback_hierarchy:
        raise ValueError("E_CAPABILITY_FALLBACK_HIERARCHY_EMPTY")

    truth_table = provider_truth_table_snapshot()
    provider_capabilities: dict[tuple[str, str], str] = {}
    for row in _provider_rows(truth_table.get("providers")):
        provider = str(row.get("provider") or "").strip()
        capabilities_payload = row.get("capabilities")
        capabilities = capabilities_payload if isinstance(capabilities_payload, dict) else {}
        for capability_name, state in capabilities.items():
            capability = str(capability_name or "").strip()
            if provider and capability:
                provider_capabilities[(provider, capability)] = str(state or "").strip().lower()

    for capability_name, rows in fallback_hierarchy.items():
        capability = str(capability_name or "").strip()
        if not capability:
            raise ValueError("E_CAPABILITY_FALLBACK_CAPABILITY_REQUIRED")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"E_CAPABILITY_FALLBACK_LIST_REQUIRED:{capability}")
        seen_providers: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"E_CAPABILITY_FALLBACK_ROW_SCHEMA:{capability}")
            provider = str(row.get("provider") or "").strip()
            state = str(row.get("state") or "").strip().lower()
            if not provider:
                raise ValueError(f"E_CAPABILITY_FALLBACK_PROVIDER_REQUIRED:{capability}")
            if provider in seen_providers:
                raise ValueError(f"E_CAPABILITY_FALLBACK_DUPLICATE_PROVIDER:{capability}:{provider}")
            seen_providers.add(provider)
            expected_state = provider_capabilities.get((provider, capability))
            if expected_state is None:
                raise ValueError(f"E_CAPABILITY_FALLBACK_PROVIDER_UNKNOWN:{capability}:{provider}")
            if expected_state != state:
                raise ValueError(f"E_CAPABILITY_FALLBACK_STATE_DRIFT:{capability}:{provider}")
            if state not in _FALLBACK_ELIGIBLE_STATES:
                raise ValueError(f"E_CAPABILITY_FALLBACK_STATE_NOT_ELIGIBLE:{capability}:{provider}")

    return hierarchy
