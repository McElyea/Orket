from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from orket.runtime.contract_bootstrap import (
    RuntimeContractSnapshots,
    load_runtime_contract_snapshots,
    write_runtime_contract_snapshots,
)
from orket.runtime.run_start_contract_artifacts import CONTRACT_SNAPSHOT_DEFS
from orket.runtime.workspace_snapshot import capture_workspace_state_snapshot
from orket.utils import sanitize_name

_DETERMINISM_RANK = {
    "pure": 0,
    "workspace": 1,
    "external": 2,
}
_RUN_IDENTITY_SCOPE = "session_bootstrap"
_RUN_IDENTITY_PROJECTION_SOURCE = "session_bootstrap_artifacts"


def capture_run_start_artifacts(
    *,
    workspace: Path,
    run_id: str,
    workload: str,
    snapshots: RuntimeContractSnapshots | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    resolved_run_id = str(run_id or "").strip()
    resolved_workload = str(workload or "").strip()
    if not resolved_run_id:
        raise ValueError("run_id is required for run-start artifacts")
    if not resolved_workload:
        raise ValueError("workload is required for run-start artifacts")

    contract_snapshots = snapshots or load_runtime_contract_snapshots()
    runtime_parent = workspace / "observability" / sanitize_name(resolved_run_id)
    runtime_root = runtime_parent / "runtime_contracts"
    staging_root = runtime_parent / "runtime_contracts_staging"
    using_staging_root = False

    if staging_root.exists():
        if runtime_root.exists():
            raise ValueError(f"E_RUN_START_ARTIFACTS_STAGING_CONFLICT:{staging_root}")
        raise ValueError(f"E_RUN_START_ARTIFACTS_INCOMPLETE:{staging_root}")

    if runtime_root.exists():
        active_root = runtime_root
    else:
        staging_root.mkdir(parents=True, exist_ok=False)
        active_root = staging_root
        using_staging_root = True

    snapshot_paths = write_runtime_contract_snapshots(
        snapshots=contract_snapshots,
        output_dir=active_root,
    )

    run_identity_path = active_root / "run_identity.json"
    run_identity = _resolve_run_identity(
        path=run_identity_path,
        run_id=resolved_run_id,
        workload=resolved_workload,
        now=now,
    )

    runtime_contract_artifacts = _write_runtime_contract_artifacts(runtime_root=active_root)

    capability_manifest = _capability_manifest_payload(
        run_id=resolved_run_id,
        snapshots=contract_snapshots,
    )
    capability_manifest_path = active_root / "capability_manifest.json"
    _write_immutable_json(
        path=capability_manifest_path,
        payload=capability_manifest,
        error_code="E_RUN_CAPABILITY_MANIFEST_IMMUTABLE",
    )

    workspace_state_snapshot_path = active_root / "workspace_state_snapshot.json"
    workspace_state_snapshot = _resolve_workspace_state_snapshot(
        path=workspace_state_snapshot_path,
        workspace=workspace,
        now=now,
    )

    if using_staging_root:
        active_root.replace(runtime_root)
        active_root = runtime_root
        snapshot_paths = _relocate_path_map(snapshot_paths, from_root=staging_root, to_root=runtime_root)
        runtime_contract_artifacts = _relocate_path_payload(
            runtime_contract_artifacts,
            from_root=staging_root,
            to_root=runtime_root,
        )
        run_identity_path = runtime_root / "run_identity.json"
        capability_manifest_path = runtime_root / "capability_manifest.json"
        workspace_state_snapshot_path = runtime_root / "workspace_state_snapshot.json"

    return {
        **contract_snapshots.as_ledger_artifacts(),
        **snapshot_paths,
        "run_identity": run_identity,
        "run_identity_path": str(run_identity_path),
        **runtime_contract_artifacts,
        "capability_manifest": capability_manifest,
        "capability_manifest_path": str(capability_manifest_path),
        "workspace_state_snapshot": workspace_state_snapshot,
        "workspace_state_snapshot_path": str(workspace_state_snapshot_path),
        "run_determinism_class": capability_manifest["run_determinism_class"],
    }


def _write_runtime_contract_artifacts(*, runtime_root: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for artifact_key, filename, factory, error_code in CONTRACT_SNAPSHOT_DEFS:
        artifact = factory()
        artifact_path = runtime_root / filename
        _write_immutable_json(
            path=artifact_path,
            payload=artifact,
            error_code=error_code,
        )
        payload[artifact_key] = artifact
        payload[f"{artifact_key}_path"] = str(artifact_path)
    return payload


def _resolve_workspace_state_snapshot(
    *,
    path: Path,
    workspace: Path,
    now: datetime | None,
) -> dict[str, Any]:
    existing = _load_json_dict(path)
    if existing is not None:
        return existing

    payload = capture_workspace_state_snapshot(workspace=workspace, now=now)
    _write_json(path, payload)
    return payload


def _resolve_run_identity(
    *,
    path: Path,
    run_id: str,
    workload: str,
    now: datetime | None,
) -> dict[str, Any]:
    existing = _load_json_dict(path)
    if existing is not None:
        existing_identity = validate_run_identity_projection(
            existing,
            error_prefix="E_RUN_IDENTITY_SCHEMA",
        )
        if existing_identity["run_id"] != run_id:
            raise ValueError("E_RUN_IDENTITY_IMMUTABLE:run_id_mismatch")
        if existing_identity["workload"] != workload:
            raise ValueError("E_RUN_IDENTITY_IMMUTABLE:workload_mismatch")
        return existing_identity

    start_time = (now or datetime.now(UTC)).isoformat()
    payload: dict[str, Any] = {
        "run_id": run_id,
        "workload": workload,
        "start_time": start_time,
        "identity_scope": _RUN_IDENTITY_SCOPE,
        "projection_source": _RUN_IDENTITY_PROJECTION_SOURCE,
        "projection_only": True,
    }
    _write_json(path, payload)
    return payload


def validate_run_identity_projection(
    value: Any,
    *,
    error_prefix: str = "run_identity",
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(_run_identity_error(error_prefix, "invalid"))

    run_id = str(value.get("run_id") or "").strip()
    workload = str(value.get("workload") or "").strip()
    start_time = str(value.get("start_time") or "").strip()
    identity_scope = str(value.get("identity_scope") or "").strip()
    projection_source = str(value.get("projection_source") or "").strip()

    if not run_id:
        raise ValueError(_run_identity_error(error_prefix, "run_id_required"))
    if not workload:
        raise ValueError(_run_identity_error(error_prefix, "workload_required"))
    if not start_time:
        raise ValueError(_run_identity_error(error_prefix, "start_time_required"))
    if identity_scope != _RUN_IDENTITY_SCOPE:
        raise ValueError(_run_identity_error(error_prefix, "identity_scope_invalid"))
    if projection_source != _RUN_IDENTITY_PROJECTION_SOURCE:
        raise ValueError(_run_identity_error(error_prefix, "projection_source_invalid"))
    if value.get("projection_only") is not True:
        raise ValueError(_run_identity_error(error_prefix, "projection_only_invalid"))

    return {
        "run_id": run_id,
        "workload": workload,
        "start_time": start_time,
        "identity_scope": _RUN_IDENTITY_SCOPE,
        "projection_source": _RUN_IDENTITY_PROJECTION_SOURCE,
        "projection_only": True,
    }


def _capability_manifest_payload(
    *,
    run_id: str,
    snapshots: RuntimeContractSnapshots,
) -> dict[str, Any]:
    tool_contracts = list(snapshots.tool_contract_snapshot.get("tool_contracts") or [])
    allowed_capabilities = sorted(
        {
            str(row.get("capability_profile") or "").strip()
            for row in tool_contracts
            if str(row.get("capability_profile") or "").strip()
        }
    )
    run_determinism_class = _least_deterministic(
        [
            str(row.get("determinism_class") or "").strip().lower()
            for row in tool_contracts
            if str(row.get("determinism_class") or "").strip()
        ]
    )
    return {
        "run_id": run_id,
        "capabilities_allowed": allowed_capabilities,
        "capabilities_used": [],
        "run_determinism_class": run_determinism_class,
        "source_tool_registry_version": snapshots.tool_registry_snapshot.get("tool_registry_version"),
        "source_tool_contract_snapshot_hash": snapshots.tool_contract_snapshot.get("snapshot_hash"),
    }


def _least_deterministic(classes: list[str]) -> str:
    if not classes:
        return "pure"
    resolved = [value for value in classes if value in _DETERMINISM_RANK]
    if not resolved:
        return "pure"
    return max(resolved, key=lambda value: _DETERMINISM_RANK[value])


def _write_immutable_json(
    *,
    path: Path,
    payload: dict[str, Any],
    error_code: str,
) -> None:
    existing = _load_json_dict(path)
    if existing is None:
        _write_json(path, payload)
        return
    if existing != payload:
        raise ValueError(f"{error_code}:{path}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_bytes((json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"E_RUN_ARTIFACT_PARSE:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"E_RUN_ARTIFACT_SCHEMA:{path}:root payload must be object")
    return dict(payload)


def _relocate_path_map(
    payload: dict[str, str],
    *,
    from_root: Path,
    to_root: Path,
) -> dict[str, str]:
    relocated: dict[str, str] = {}
    for key, value in payload.items():
        candidate = Path(value)
        if candidate.is_relative_to(from_root):
            candidate = to_root / candidate.relative_to(from_root)
        relocated[key] = str(candidate)
    return relocated


def _relocate_path_payload(
    payload: dict[str, Any],
    *,
    from_root: Path,
    to_root: Path,
) -> dict[str, Any]:
    relocated: dict[str, Any] = {}
    for key, value in payload.items():
        if key.endswith("_path") and isinstance(value, str):
            candidate = Path(value)
            if candidate.is_relative_to(from_root):
                relocated[key] = str(to_root / candidate.relative_to(from_root))
                continue
        relocated[key] = value
    return relocated


def _run_identity_error(prefix: str, detail: str) -> str:
    separator = ":" if prefix.startswith("E_") else "_"
    return f"{prefix}{separator}{detail}"
