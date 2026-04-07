from __future__ import annotations

from typing import Any, Final

DRIFT_SCHEMA_VERSION: Final[str] = "1.0"

DRIFT_LAYER_PRECEDENCE: Final[tuple[str, ...]] = (
    "runtime_contract_drift",
    "tool_schema_drift",
    "prompt_drift",
    "tool_behavior_drift",
    "artifact_formatting_drift",
)

RUNTIME_DRIFT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "ledger_schema_version",
        "runtime_contract_hash",
        "runtime_policy_versions",
    }
)

TOOL_SCHEMA_DRIFT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "tool_schema_hash",
        "tool_registry_version",
        "artifact_schema_registry_version",
        "compatibility_map_schema_version",
        "tool_registry_snapshot_hash",
        "artifact_schema_snapshot_hash",
        "tool_contract_snapshot_hash",
        "capability_manifest_source_tool_registry_version",
        "capability_manifest_source_tool_contract_snapshot_hash",
    }
)

PROMPT_DRIFT_FIELDS: Final[frozenset[str]] = frozenset({"prompt_hash", "prompt_structure", "proposal_hash"})

TOOL_BEHAVIOR_DRIFT_FIELDS: Final[frozenset[str]] = frozenset(
    {"status", "failure_class", "failure_reason", "operations"}
)

ARTIFACT_FORMAT_DRIFT_FIELDS: Final[frozenset[str]] = frozenset({"artifact_inventory", "receipt_inventory"})


def classify_replay_drift(*, differences: list[dict[str, Any]]) -> dict[str, Any]:
    layer_hits: dict[str, set[str]] = {layer: set() for layer in DRIFT_LAYER_PRECEDENCE}
    unclassified_fields: set[str] = set()

    for difference in differences:
        field = str(difference.get("field") or "").strip()
        if not field:
            continue

        if field in RUNTIME_DRIFT_FIELDS:
            layer_hits["runtime_contract_drift"].add(field)
            continue
        if field in TOOL_SCHEMA_DRIFT_FIELDS:
            layer_hits["tool_schema_drift"].add(field)
            continue
        if field in PROMPT_DRIFT_FIELDS:
            layer_hits["prompt_drift"].add(field)
            continue
        if field in TOOL_BEHAVIOR_DRIFT_FIELDS:
            layer_hits["tool_behavior_drift"].add(field)
            continue
        if field in ARTIFACT_FORMAT_DRIFT_FIELDS:
            layer_hits["artifact_formatting_drift"].add(field)
            continue
        if field == "compatibility_validation":
            _classify_compatibility_validation_difference(layer_hits=layer_hits, difference=difference)
            continue
        unclassified_fields.add(field)

    if not any(layer_hits.values()) and unclassified_fields:
        layer_hits["tool_behavior_drift"].update(unclassified_fields)

    detected_layers = [layer for layer in DRIFT_LAYER_PRECEDENCE if layer_hits[layer]]
    primary_layer = detected_layers[0] if detected_layers else "none"
    return {
        "drift_schema_version": DRIFT_SCHEMA_VERSION,
        "drift_detected": bool(differences),
        "primary_layer": primary_layer,
        "detected_layers": detected_layers,
        "layer_reasons": [
            {"layer": layer, "fields": sorted(layer_hits[layer])}
            for layer in DRIFT_LAYER_PRECEDENCE
            if layer_hits[layer]
        ],
        "unclassified_fields": sorted(unclassified_fields),
    }


def _classify_compatibility_validation_difference(
    *,
    layer_hits: dict[str, set[str]],
    difference: dict[str, Any],
) -> None:
    structured_fields = _compatibility_surface_fields(difference)
    if not structured_fields:
        layer_hits["runtime_contract_drift"].add("compatibility_validation")
        return

    for field in structured_fields:
        if field == "runtime_contract_hash" or field.startswith("runtime_policy_versions."):
            layer_hits["runtime_contract_drift"].add(f"compatibility_validation.{field}")
            continue
        if field in TOOL_SCHEMA_DRIFT_FIELDS:
            layer_hits["tool_schema_drift"].add(f"compatibility_validation.{field}")
            continue
        if field.startswith("capability_manifest."):
            layer_hits["tool_schema_drift"].add(f"compatibility_validation.{field}")
            continue
        if field.startswith("workspace_state_snapshot."):
            layer_hits["artifact_formatting_drift"].add(f"compatibility_validation.{field}")
            continue
        if field == "lifecycle_missing":
            layer_hits["runtime_contract_drift"].add("compatibility_validation.lifecycle_missing")
            continue
        layer_hits["runtime_contract_drift"].add(f"compatibility_validation.{field}")


def _compatibility_surface_fields(difference: dict[str, Any]) -> set[str]:
    discovered: set[str] = set()
    for side in ("a", "b"):
        payload = difference.get(side)
        if not isinstance(payload, dict):
            continue
        discovered.update(_compatibility_side_fields(payload))
    return discovered


def _compatibility_side_fields(payload: dict[str, Any]) -> set[str]:
    discovered: set[str] = set()
    for key in ("mismatch_fields", "missing_contract_fields"):
        values = payload.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value or "").strip()
            if text:
                discovered.add(text)
    lifecycle_missing = payload.get("lifecycle_missing")
    if isinstance(lifecycle_missing, list) and lifecycle_missing:
        discovered.add("lifecycle_missing")
    return discovered
