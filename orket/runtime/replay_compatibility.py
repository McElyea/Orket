from __future__ import annotations

from typing import Any

REPLAY_COMPATIBILITY_REQUIRED_FIELDS = (
    "tool_registry_version",
    "artifact_schema_registry_version",
    "compatibility_map_schema_version",
    "tool_registry_snapshot_hash",
    "artifact_schema_snapshot_hash",
    "tool_contract_snapshot_hash",
)


def resolve_ledger_schema_version(events: list[dict[str, Any]]) -> str:
    observed = {
        str(event.get("ledger_schema_version") or "1.0").strip()
        for event in events
        if str(event.get("ledger_schema_version") or "1.0").strip()
    }
    if not observed:
        return "1.0"
    if len(observed) > 1:
        raise ValueError("E_REPLAY_LEDGER_SCHEMA_INCOMPATIBLE:multiple_versions")
    version = next(iter(observed))
    if version != "1.0":
        raise ValueError(f"E_REPLAY_LEDGER_SCHEMA_INCOMPATIBLE:{version}")
    return version


def evaluate_replay_compatibility(
    *,
    events: list[dict[str, Any]],
    current_contract_snapshots: dict[str, Any],
    current_policy_versions: dict[str, Any],
    current_runtime_contract_hash: str,
    enforce_runtime_contract_compatibility: bool,
    require_replay_artifact_completeness: bool,
) -> dict[str, Any]:
    lifecycle_missing: list[str] = []
    if not any(str(event.get("kind") or "") == "run_started" for event in events):
        lifecycle_missing.append("run_started")
    if not any(str(event.get("kind") or "") == "run_finalized" for event in events):
        lifecycle_missing.append("run_finalized")
    if lifecycle_missing and require_replay_artifact_completeness:
        raise ValueError(f"E_REPLAY_INCOMPLETE:{','.join(lifecycle_missing)}")

    run_started_artifacts = _extract_run_started_artifacts(events)
    recorded = _recorded_replay_contract_surface(run_started_artifacts)
    missing_contract_fields = [
        key for key in REPLAY_COMPATIBILITY_REQUIRED_FIELDS if not str(recorded.get(key) or "").strip()
    ]
    mismatch_fields: list[str] = []
    for field in REPLAY_COMPATIBILITY_REQUIRED_FIELDS:
        recorded_value = str(recorded.get(field) or "").strip()
        if not recorded_value:
            continue
        current_value = str(current_contract_snapshots.get(field) or "").strip()
        if recorded_value != current_value:
            mismatch_fields.append(field)

    recorded_policies = dict(recorded.get("runtime_policy_versions") or {})
    if recorded_policies:
        for key in sorted(set(recorded_policies.keys()) | set(current_policy_versions.keys())):
            left = str(recorded_policies.get(key) or "")
            right = str(current_policy_versions.get(key) or "")
            if left != right:
                mismatch_fields.append(f"runtime_policy_versions.{key}")

    recorded_contract_hash = str(recorded.get("runtime_contract_hash") or "").strip()
    if recorded_contract_hash and recorded_contract_hash != str(current_runtime_contract_hash):
        mismatch_fields.append("runtime_contract_hash")

    if mismatch_fields and enforce_runtime_contract_compatibility:
        raise ValueError(f"E_REPLAY_COMPATIBILITY_MISMATCH:{','.join(mismatch_fields)}")
    if missing_contract_fields and enforce_runtime_contract_compatibility and require_replay_artifact_completeness:
        raise ValueError(f"E_REPLAY_ARTIFACTS_MISSING:{','.join(missing_contract_fields)}")

    path = "primary"
    if missing_contract_fields:
        path = "degraded"
    if mismatch_fields:
        path = "blocked"
    return {
        "path": path,
        "status": "ok" if not mismatch_fields else "mismatch",
        "missing_contract_fields": missing_contract_fields,
        "mismatch_fields": mismatch_fields,
        "lifecycle_missing": lifecycle_missing,
    }


def _extract_run_started_artifacts(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if str(event.get("kind") or "") != "run_started":
            continue
        artifacts = event.get("artifacts")
        if isinstance(artifacts, dict):
            return dict(artifacts)
    return {}


def _recorded_replay_contract_surface(artifacts: dict[str, Any]) -> dict[str, Any]:
    tool_registry = artifacts.get("tool_registry_snapshot")
    artifact_schema = artifacts.get("artifact_schema_snapshot")
    compatibility_map_schema = artifacts.get("compatibility_map_schema_snapshot")
    tool_contract_snapshot = artifacts.get("tool_contract_snapshot")
    policies = artifacts.get("runtime_policy_versions")
    return {
        "tool_registry_version": str((tool_registry or {}).get("tool_registry_version") or "")
        if isinstance(tool_registry, dict)
        else "",
        "artifact_schema_registry_version": str((artifact_schema or {}).get("artifact_schema_registry_version") or "")
        if isinstance(artifact_schema, dict)
        else "",
        "compatibility_map_schema_version": str((compatibility_map_schema or {}).get("schema_version") or "")
        if isinstance(compatibility_map_schema, dict)
        else "",
        "tool_registry_snapshot_hash": str((tool_registry or {}).get("snapshot_hash") or "")
        if isinstance(tool_registry, dict)
        else "",
        "artifact_schema_snapshot_hash": str((artifact_schema or {}).get("snapshot_hash") or "")
        if isinstance(artifact_schema, dict)
        else "",
        "tool_contract_snapshot_hash": str((tool_contract_snapshot or {}).get("snapshot_hash") or "")
        if isinstance(tool_contract_snapshot, dict)
        else "",
        "runtime_policy_versions": dict(policies) if isinstance(policies, dict) else {},
        "runtime_contract_hash": str(artifacts.get("runtime_contract_hash") or ""),
    }
