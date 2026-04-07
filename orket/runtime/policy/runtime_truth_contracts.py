from __future__ import annotations

from typing import Any

RUNTIME_STATUS_VOCABULARY_SCHEMA_VERSION = "1.0"
DEGRADATION_TAXONOMY_SCHEMA_VERSION = "1.0"
FAIL_BEHAVIOR_REGISTRY_SCHEMA_VERSION = "1.0"

RUNTIME_STATUS_VOCABULARY: tuple[str, ...] = (
    "running",
    "done",
    "failed",
    "terminal_failure",
    "incomplete",
    "blocked",
    "degraded",
)

_EXPECTED_DEGRADATION_LEVELS = {"none", "degraded", "blocked"}
_ALLOWED_FAIL_BEHAVIOR_MODES = {"fail_open", "fail_closed"}


def _normalized_strings(value: object, *, lowercase: bool = False) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for token in value:
        item = str(token).strip()
        if item:
            normalized.append(item.lower() if lowercase else item)
    return normalized


def _normalized_dict_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in value:
        if isinstance(row, dict):
            rows.append({str(key): item for key, item in row.items()})
    return rows


def runtime_status_vocabulary_snapshot() -> dict[str, object]:
    return {
        "schema_version": RUNTIME_STATUS_VOCABULARY_SCHEMA_VERSION,
        "runtime_status_terms": list(RUNTIME_STATUS_VOCABULARY),
    }


def validate_runtime_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized not in RUNTIME_STATUS_VOCABULARY:
        raise ValueError(f"E_RUNTIME_STATUS_UNKNOWN:{normalized or '<empty>'}")
    return normalized


def validate_runtime_status_vocabulary_contract(
    payload: dict[str, object] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or runtime_status_vocabulary_snapshot())
    terms = _normalized_strings(contract.get("runtime_status_terms"), lowercase=True)
    if not terms:
        raise ValueError("E_RUNTIME_STATUS_VOCABULARY_EMPTY")
    if len(set(terms)) != len(terms):
        raise ValueError("E_RUNTIME_STATUS_VOCABULARY_DUPLICATE")
    if set(terms) != set(RUNTIME_STATUS_VOCABULARY):
        raise ValueError("E_RUNTIME_STATUS_VOCABULARY_SET_MISMATCH")
    return tuple(sorted(terms))


def degradation_taxonomy_snapshot() -> dict[str, object]:
    return {
        "schema_version": DEGRADATION_TAXONOMY_SCHEMA_VERSION,
        "levels": [
            {
                "level": "none",
                "description": "No known runtime degradation in the active execution path.",
                "path_classification": "primary",
            },
            {
                "level": "degraded",
                "description": "Execution completed with reduced guarantees or optional feature loss.",
                "path_classification": "degraded",
            },
            {
                "level": "blocked",
                "description": "Execution path is unavailable; runtime halted before completion.",
                "path_classification": "blocked",
            },
        ],
    }


def validate_degradation_taxonomy_contract(
    payload: dict[str, object] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or degradation_taxonomy_snapshot())
    rows = _normalized_dict_rows(contract.get("levels"))
    if not rows:
        raise ValueError("E_DEGRADATION_TAXONOMY_EMPTY")
    levels: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_DEGRADATION_TAXONOMY_ROW_SCHEMA")
        level = str(row.get("level") or "").strip().lower()
        description = str(row.get("description") or "").strip()
        path_classification = str(row.get("path_classification") or "").strip().lower()
        if not level or not description or not path_classification:
            raise ValueError("E_DEGRADATION_TAXONOMY_ROW_SCHEMA")
        levels.append(level)
    if len(set(levels)) != len(levels):
        raise ValueError("E_DEGRADATION_TAXONOMY_DUPLICATE_LEVEL")
    if set(levels) != _EXPECTED_DEGRADATION_LEVELS:
        raise ValueError("E_DEGRADATION_TAXONOMY_LEVEL_SET_MISMATCH")
    return tuple(sorted(levels))


def fail_behavior_registry_snapshot() -> dict[str, object]:
    return {
        "schema_version": FAIL_BEHAVIOR_REGISTRY_SCHEMA_VERSION,
        "subsystems": [
            {
                "subsystem": "runtime_contract_bootstrap",
                "failure_mode": "fail_closed",
                "reason": "Run startup must stop when contract snapshots or run-start artifacts are invalid.",
            },
            {
                "subsystem": "state_backend_mode_validation",
                "failure_mode": "fail_closed",
                "reason": "Invalid or unready state backend configuration must block execution startup.",
            },
            {
                "subsystem": "protocol_receipt_materialization",
                "failure_mode": "fail_open",
                "reason": "Receipt projection errors are logged and run finalization continues.",
            },
            {
                "subsystem": "artifact_export",
                "failure_mode": "fail_open",
                "reason": "Artifact export errors are logged and do not block run finalization.",
            },
        ],
    }


def validate_fail_behavior_registry_contract(
    payload: dict[str, object] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or fail_behavior_registry_snapshot())
    rows = _normalized_dict_rows(contract.get("subsystems"))
    if not rows:
        raise ValueError("E_FAIL_BEHAVIOR_REGISTRY_EMPTY")
    subsystems: list[str] = []
    modes: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_FAIL_BEHAVIOR_REGISTRY_ROW_SCHEMA")
        subsystem = str(row.get("subsystem") or "").strip()
        failure_mode = str(row.get("failure_mode") or "").strip().lower()
        reason = str(row.get("reason") or "").strip()
        if not subsystem or not reason:
            raise ValueError("E_FAIL_BEHAVIOR_REGISTRY_ROW_SCHEMA")
        if failure_mode not in _ALLOWED_FAIL_BEHAVIOR_MODES:
            raise ValueError(f"E_FAIL_BEHAVIOR_REGISTRY_MODE_INVALID:{subsystem}")
        subsystems.append(subsystem)
        modes.add(failure_mode)
    if len(set(subsystems)) != len(subsystems):
        raise ValueError("E_FAIL_BEHAVIOR_REGISTRY_DUPLICATE_SUBSYSTEM")
    if modes != _ALLOWED_FAIL_BEHAVIOR_MODES:
        raise ValueError("E_FAIL_BEHAVIOR_REGISTRY_MODE_SET_MISMATCH")
    return tuple(sorted(subsystems))
