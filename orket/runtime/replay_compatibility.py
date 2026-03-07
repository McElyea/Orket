from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.runtime.workspace_snapshot import capture_workspace_state_snapshot

REPLAY_COMPATIBILITY_REQUIRED_FIELDS = (
    "tool_registry_version",
    "artifact_schema_registry_version",
    "compatibility_map_schema_version",
    "tool_registry_snapshot_hash",
    "artifact_schema_snapshot_hash",
    "tool_contract_snapshot_hash",
    "capability_manifest_source_tool_registry_version",
    "capability_manifest_source_tool_contract_snapshot_hash",
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
        current_value = _current_compatibility_value(field=field, current_contract_snapshots=current_contract_snapshots)
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

    run_determinism_class = str(recorded.get("run_determinism_class") or "").strip().lower()
    workspace_required = run_determinism_class in {"workspace", "external"}
    if workspace_required:
        missing_contract_fields.extend(_workspace_missing_fields(recorded))
        if enforce_runtime_contract_compatibility:
            mismatch_fields.extend(_workspace_mismatch_fields(recorded))

    missing_contract_fields = sorted(set(missing_contract_fields))
    mismatch_fields = sorted(set(mismatch_fields))

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
        "run_determinism_class": run_determinism_class,
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
    capability_manifest = artifacts.get("capability_manifest")
    policies = artifacts.get("runtime_policy_versions")
    run_determinism_class = ""
    if isinstance(capability_manifest, dict):
        run_determinism_class = str(capability_manifest.get("run_determinism_class") or "").strip().lower()
    if not run_determinism_class:
        run_determinism_class = str(artifacts.get("run_determinism_class") or "").strip().lower()
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
        "capability_manifest_source_tool_registry_version": str(
            (capability_manifest or {}).get("source_tool_registry_version") or ""
        )
        if isinstance(capability_manifest, dict)
        else "",
        "capability_manifest_source_tool_contract_snapshot_hash": str(
            (capability_manifest or {}).get("source_tool_contract_snapshot_hash") or ""
        )
        if isinstance(capability_manifest, dict)
        else "",
        "runtime_policy_versions": dict(policies) if isinstance(policies, dict) else {},
        "runtime_contract_hash": str(artifacts.get("runtime_contract_hash") or ""),
        "run_determinism_class": run_determinism_class,
        "workspace_state_snapshot": _workspace_snapshot_payload(artifacts),
    }


def _workspace_snapshot_payload(artifacts: dict[str, Any]) -> dict[str, Any]:
    payload = artifacts.get("workspace_state_snapshot")
    if not isinstance(payload, dict):
        payload = {}
    snapshot = dict(payload)
    workspace_path = str(snapshot.get("workspace_path") or artifacts.get("workspace") or "").strip()
    if workspace_path:
        snapshot["workspace_path"] = workspace_path
    return snapshot


def _current_compatibility_value(
    *,
    field: str,
    current_contract_snapshots: dict[str, Any],
) -> str:
    if field == "capability_manifest_source_tool_registry_version":
        return str(current_contract_snapshots.get("tool_registry_version") or "").strip()
    if field == "capability_manifest_source_tool_contract_snapshot_hash":
        return str(current_contract_snapshots.get("tool_contract_snapshot_hash") or "").strip()
    return str(current_contract_snapshots.get(field) or "").strip()


def _workspace_missing_fields(recorded: dict[str, Any]) -> list[str]:
    snapshot = recorded.get("workspace_state_snapshot")
    if not isinstance(snapshot, dict):
        return ["workspace_state_snapshot"]

    missing: list[str] = []
    if not str(snapshot.get("workspace_path") or "").strip():
        missing.append("workspace_state_snapshot.workspace_path")
    if not str(snapshot.get("workspace_hash") or "").strip():
        missing.append("workspace_state_snapshot.workspace_hash")
    if not str(snapshot.get("workspace_type") or "").strip():
        missing.append("workspace_state_snapshot.workspace_type")
    try:
        _ = int(snapshot.get("file_count"))
    except (TypeError, ValueError):
        missing.append("workspace_state_snapshot.file_count")
    return missing


def _workspace_mismatch_fields(recorded: dict[str, Any]) -> list[str]:
    snapshot = recorded.get("workspace_state_snapshot")
    if not isinstance(snapshot, dict):
        return []

    workspace_path = Path(str(snapshot.get("workspace_path") or "").strip())
    expected_hash = str(snapshot.get("workspace_hash") or "").strip()
    expected_type = str(snapshot.get("workspace_type") or "").strip()
    try:
        expected_count = int(snapshot.get("file_count"))
    except (TypeError, ValueError):
        expected_count = -1

    if not str(workspace_path).strip():
        return []
    if not workspace_path.exists() or not workspace_path.is_dir():
        return ["workspace_state_snapshot.workspace_path"]
    try:
        observed = capture_workspace_state_snapshot(workspace=workspace_path)
    except (OSError, ValueError):
        return ["workspace_state_snapshot.workspace_path"]

    mismatch: list[str] = []
    if expected_type and str(observed.get("workspace_type") or "") != expected_type:
        mismatch.append("workspace_state_snapshot.workspace_type")
    if expected_hash and str(observed.get("workspace_hash") or "") != expected_hash:
        mismatch.append("workspace_state_snapshot.workspace_hash")
    if expected_count >= 0 and int(observed.get("file_count") or 0) != expected_count:
        mismatch.append("workspace_state_snapshot.file_count")
    return mismatch
