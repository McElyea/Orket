from __future__ import annotations


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
