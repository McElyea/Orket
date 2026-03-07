from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from orket.application.workflows.protocol_hashing import hash_canonical_json


DEFAULT_ARTIFACT_SCHEMA_REGISTRY_PATH = Path("core/artifacts/schema_registry.yaml")
DEFAULT_COMPATIBILITY_MAP_PATH = Path("core/tools/compatibility_map.yaml")
DEFAULT_COMPATIBILITY_MAP_SCHEMA_PATH = Path("core/tools/compatibility_map_schema.yaml")
DEFAULT_TOOL_REGISTRY_PATH = Path("core/tools/tool_registry.yaml")

TOOL_DETERMINISM_CLASSES = {"pure", "workspace", "external"}
TOOL_RING_CLASSES = {"core", "compatibility", "experimental"}
DETERMINISM_RANK = {"pure": 0, "workspace": 1, "external": 2}


@dataclass(frozen=True)
class RuntimeContractSnapshots:
    tool_registry_snapshot: dict[str, Any]
    artifact_schema_snapshot: dict[str, Any]
    tool_contract_snapshot: dict[str, Any]
    compatibility_map_schema_snapshot: dict[str, Any]
    compatibility_map_snapshot: dict[str, Any]

    def as_ledger_artifacts(self) -> dict[str, Any]:
        return {
            "tool_registry_snapshot": dict(self.tool_registry_snapshot),
            "artifact_schema_snapshot": dict(self.artifact_schema_snapshot),
            "tool_contract_snapshot": dict(self.tool_contract_snapshot),
            "compatibility_map_schema_snapshot": dict(self.compatibility_map_schema_snapshot),
            "compatibility_map_snapshot": dict(self.compatibility_map_snapshot),
        }


def parse_contract_version(value: Any, *, field_name: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError(f"{field_name} is required")
    parts = token.split(".")
    if not all(part.isdigit() for part in parts):
        raise ValueError(f"{field_name} must be a dot-separated numeric version")
    return ".".join(str(int(part)) for part in parts)


def load_runtime_contract_snapshots(
    *,
    artifact_schema_registry_path: Path | str = DEFAULT_ARTIFACT_SCHEMA_REGISTRY_PATH,
    compatibility_map_path: Path | str = DEFAULT_COMPATIBILITY_MAP_PATH,
    compatibility_map_schema_path: Path | str = DEFAULT_COMPATIBILITY_MAP_SCHEMA_PATH,
    tool_registry_path: Path | str = DEFAULT_TOOL_REGISTRY_PATH,
) -> RuntimeContractSnapshots:
    artifact_registry = _load_yaml_dict(Path(artifact_schema_registry_path))
    tool_registry = _load_yaml_dict(Path(tool_registry_path))
    compatibility_schema = _load_yaml_dict(Path(compatibility_map_schema_path))
    compatibility_map = _load_yaml_dict(Path(compatibility_map_path))

    artifact_registry_version, artifact_versions = _parse_artifact_schema_registry(artifact_registry)
    tool_registry_version, tools = _parse_tool_registry(tool_registry)
    parsed_compatibility_schema = _parse_compatibility_map_schema(compatibility_schema)
    parsed_compatibility_map = _parse_compatibility_map(
        compatibility_map,
        schema=parsed_compatibility_schema,
        tools=tools,
    )

    artifact_snapshot = {
        "artifact_schema_registry_version": artifact_registry_version,
        "artifacts": sorted(artifact_versions.keys()),
        "artifact_versions": dict(sorted(artifact_versions.items())),
    }
    artifact_snapshot["snapshot_hash"] = hash_canonical_json(artifact_snapshot)

    tool_registry_snapshot = {
        "tool_registry_version": tool_registry_version,
        "tools": [row["tool_name"] for row in tools],
    }
    tool_registry_snapshot["snapshot_hash"] = hash_canonical_json(tool_registry_snapshot)

    tool_contract_snapshot = {
        "tool_registry_version": tool_registry_version,
        "tool_contracts": [
            {
                "tool_name": row["tool_name"],
                "ring": row["ring"],
                "tool_contract_version": row["tool_contract_version"],
                "determinism_class": row["determinism_class"],
                "capability_profile": row["capability_profile"],
            }
            for row in tools
        ],
    }
    tool_contract_snapshot["snapshot_hash"] = hash_canonical_json(tool_contract_snapshot)

    compatibility_map_schema_snapshot = {
        "schema_version": parsed_compatibility_schema["schema_version"],
        "compatibility_map_version": parsed_compatibility_schema["compatibility_map_version"],
        "required_fields": list(parsed_compatibility_schema["required_fields"]),
        "allowed_determinism_classes": list(parsed_compatibility_schema["allowed_determinism_classes"]),
        "mapping_count": len(parsed_compatibility_map),
        "mappings": [row["compat_tool_name"] for row in parsed_compatibility_map],
    }
    compatibility_map_schema_snapshot["snapshot_hash"] = hash_canonical_json(compatibility_map_schema_snapshot)

    compatibility_map_snapshot = {
        "schema_version": parsed_compatibility_schema["compatibility_map_version"],
        "mapping_count": len(parsed_compatibility_map),
        "mappings": {
            row["compat_tool_name"]: {
                "mapping_version": row["mapping_version"],
                "mapped_core_tools": list(row["mapped_core_tools"]),
                "schema_compatibility_range": row["schema_compatibility_range"],
                "determinism_class": row["determinism_class"],
            }
            for row in parsed_compatibility_map
        },
    }
    compatibility_map_snapshot["snapshot_hash"] = hash_canonical_json(compatibility_map_snapshot)

    return RuntimeContractSnapshots(
        tool_registry_snapshot=tool_registry_snapshot,
        artifact_schema_snapshot=artifact_snapshot,
        tool_contract_snapshot=tool_contract_snapshot,
        compatibility_map_schema_snapshot=compatibility_map_schema_snapshot,
        compatibility_map_snapshot=compatibility_map_snapshot,
    )


def write_runtime_contract_snapshots(
    *,
    snapshots: RuntimeContractSnapshots,
    output_dir: Path | str,
) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    file_map = {
        "tool_registry_snapshot_path": destination / "tool_registry_snapshot.json",
        "artifact_schema_snapshot_path": destination / "artifact_schema_snapshot.json",
        "tool_contract_snapshot_path": destination / "tool_contract_snapshot.json",
        "compatibility_map_schema_snapshot_path": destination / "compatibility_map_schema_snapshot.json",
        "compatibility_map_snapshot_path": destination / "compatibility_map_snapshot.json",
    }
    payloads = {
        "tool_registry_snapshot_path": snapshots.tool_registry_snapshot,
        "artifact_schema_snapshot_path": snapshots.artifact_schema_snapshot,
        "tool_contract_snapshot_path": snapshots.tool_contract_snapshot,
        "compatibility_map_schema_snapshot_path": snapshots.compatibility_map_schema_snapshot,
        "compatibility_map_snapshot_path": snapshots.compatibility_map_snapshot,
    }

    for key, path in file_map.items():
        payload = payloads[key]
        path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return {key: str(path) for key, path in file_map.items()}


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"runtime_contract_load:{path}:{exc}") from exc
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"runtime_contract_parse:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"runtime_contract_schema:{path}:root payload must be a mapping")
    return dict(payload)


def _parse_artifact_schema_registry(payload: dict[str, Any]) -> tuple[str, dict[str, str]]:
    registry_version = parse_contract_version(payload.get("registry_version"), field_name="artifact registry_version")
    artifacts_raw = payload.get("artifacts")
    if not isinstance(artifacts_raw, dict) or not artifacts_raw:
        raise ValueError("artifact registry artifacts must be a non-empty mapping")

    artifacts: dict[str, str] = {}
    for artifact_name, schema_version in artifacts_raw.items():
        normalized_name = str(artifact_name or "").strip()
        if not normalized_name:
            raise ValueError("artifact registry contains an empty artifact name")
        artifacts[normalized_name] = parse_contract_version(
            schema_version,
            field_name=f"artifact schema version for {normalized_name}",
        )
    return registry_version, artifacts


def _parse_tool_registry(payload: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    registry_version = parse_contract_version(payload.get("tool_registry_version"), field_name="tool_registry_version")
    tools_raw = payload.get("tools")
    if not isinstance(tools_raw, list) or not tools_raw:
        raise ValueError("tool registry tools must be a non-empty list")

    seen_names: set[str] = set()
    tools: list[dict[str, str]] = []
    for index, row in enumerate(tools_raw):
        if not isinstance(row, dict):
            raise ValueError(f"tool registry entry {index} must be an object")

        tool_name = str(row.get("tool_name") or "").strip()
        if not tool_name:
            raise ValueError(f"tool registry entry {index} has empty tool_name")
        if tool_name in seen_names:
            raise ValueError(f"tool registry contains duplicate tool_name: {tool_name}")
        seen_names.add(tool_name)

        ring = str(row.get("ring") or "").strip().lower()
        if ring not in TOOL_RING_CLASSES:
            raise ValueError(f"tool registry tool '{tool_name}' has unsupported ring '{ring}'")

        determinism_class = str(row.get("determinism_class") or "").strip().lower()
        if determinism_class not in TOOL_DETERMINISM_CLASSES:
            raise ValueError(
                f"tool registry tool '{tool_name}' has unsupported determinism_class '{determinism_class}'"
            )

        capability_profile = str(row.get("capability_profile") or "").strip()
        if not capability_profile:
            raise ValueError(f"tool registry tool '{tool_name}' requires capability_profile")

        tools.append(
            {
                "tool_name": tool_name,
                "ring": ring,
                "tool_contract_version": parse_contract_version(
                    row.get("tool_contract_version"),
                    field_name=f"tool_contract_version for {tool_name}",
                ),
                "determinism_class": determinism_class,
                "capability_profile": capability_profile,
            }
        )
    tools.sort(key=lambda item: item["tool_name"])
    return registry_version, tools


def _parse_compatibility_map_schema(payload: dict[str, Any]) -> dict[str, Any]:
    schema_version = parse_contract_version(payload.get("schema_version"), field_name="compatibility schema_version")
    compatibility_map_version = parse_contract_version(
        payload.get("compatibility_map_version"),
        field_name="compatibility_map_version",
    )
    required_fields = _parse_non_empty_string_list(payload.get("required_fields"), field_name="required_fields")
    allowed_determinism = _parse_non_empty_string_list(
        payload.get("allowed_determinism_classes"),
        field_name="allowed_determinism_classes",
    )
    normalized_allowed = [value.lower() for value in allowed_determinism]
    for value in normalized_allowed:
        if value not in TOOL_DETERMINISM_CLASSES:
            raise ValueError(f"compatibility schema has unsupported determinism class '{value}'")

    allowed_target_ring = str(payload.get("allowed_target_ring") or "").strip().lower()
    if allowed_target_ring not in TOOL_RING_CLASSES:
        raise ValueError(f"compatibility schema has unsupported allowed_target_ring '{allowed_target_ring}'")

    return {
        "schema_version": schema_version,
        "compatibility_map_version": compatibility_map_version,
        "required_fields": required_fields,
        "allowed_determinism_classes": normalized_allowed,
        "allowed_target_ring": allowed_target_ring,
    }


def _parse_compatibility_map(
    payload: dict[str, Any],
    *,
    schema: dict[str, Any],
    tools: list[dict[str, str]],
) -> list[dict[str, Any]]:
    map_version = parse_contract_version(payload.get("schema_version"), field_name="compatibility map schema_version")
    expected_version = str(schema["compatibility_map_version"])
    if map_version != expected_version:
        raise ValueError(
            f"compatibility map schema_version '{map_version}' does not match expected '{expected_version}'"
        )

    mappings_raw = payload.get("mappings")
    if not isinstance(mappings_raw, dict):
        raise ValueError("compatibility map mappings must be a mapping")

    tool_index = {row["tool_name"]: dict(row) for row in tools}
    required_fields = set(schema["required_fields"])
    allowed_determinism = set(schema["allowed_determinism_classes"])
    allowed_target_ring = str(schema["allowed_target_ring"])

    parsed: list[dict[str, Any]] = []
    for compat_tool_name in sorted(mappings_raw.keys()):
        mapping = mappings_raw[compat_tool_name]
        normalized_compat_tool_name = str(compat_tool_name or "").strip()
        if not normalized_compat_tool_name:
            raise ValueError("compatibility map contains an empty compat_tool_name")
        if not isinstance(mapping, dict):
            raise ValueError(f"compatibility mapping '{normalized_compat_tool_name}' must be an object")

        missing_fields = sorted(field for field in required_fields if field not in mapping)
        if missing_fields:
            raise ValueError(
                f"compatibility mapping '{normalized_compat_tool_name}' missing fields: {','.join(missing_fields)}"
            )

        mapping_version = mapping.get("mapping_version")
        if not isinstance(mapping_version, int) or mapping_version <= 0:
            raise ValueError(f"compatibility mapping '{normalized_compat_tool_name}' has invalid mapping_version")

        mapped_core_tools = _parse_non_empty_string_list(
            mapping.get("mapped_core_tools"),
            field_name=f"mapped_core_tools for {normalized_compat_tool_name}",
        )
        mapped_tool_determinism: list[str] = []
        for mapped_tool in mapped_core_tools:
            tool_entry = tool_index.get(mapped_tool)
            if tool_entry is None:
                raise ValueError(
                    f"compatibility mapping '{normalized_compat_tool_name}' references unknown tool '{mapped_tool}'"
                )
            if str(tool_entry["ring"]) != allowed_target_ring:
                raise ValueError(
                    f"compatibility mapping '{normalized_compat_tool_name}' maps to non-{allowed_target_ring} tool "
                    f"'{mapped_tool}'"
                )
            mapped_tool_determinism.append(str(tool_entry["determinism_class"]))

        determinism_class = str(mapping.get("determinism_class") or "").strip().lower()
        if determinism_class not in allowed_determinism:
            raise ValueError(
                f"compatibility mapping '{normalized_compat_tool_name}' has unsupported determinism_class "
                f"'{determinism_class}'"
            )
        least_mapped_determinism = _least_deterministic(mapped_tool_determinism)
        if determinism_class != least_mapped_determinism:
            raise ValueError(
                "compatibility mapping "
                f"'{normalized_compat_tool_name}' determinism_class '{determinism_class}' does not match "
                f"least mapped determinism '{least_mapped_determinism}'"
            )

        schema_compatibility_range = str(mapping.get("schema_compatibility_range") or "").strip()
        if not schema_compatibility_range:
            raise ValueError(
                f"compatibility mapping '{normalized_compat_tool_name}' requires schema_compatibility_range"
            )

        parsed.append(
            {
                "compat_tool_name": normalized_compat_tool_name,
                "mapping_version": mapping_version,
                "mapped_core_tools": mapped_core_tools,
                "schema_compatibility_range": schema_compatibility_range,
                "determinism_class": determinism_class,
            }
        )
    return parsed


def _parse_non_empty_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")
    rows: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        token = str(raw or "").strip()
        if not token:
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")
        if token in seen:
            continue
        seen.add(token)
        rows.append(token)
    return rows


def _least_deterministic(classes: list[str]) -> str:
    resolved = [value for value in classes if value in DETERMINISM_RANK]
    if not resolved:
        return "pure"
    return max(resolved, key=lambda value: DETERMINISM_RANK[value])
