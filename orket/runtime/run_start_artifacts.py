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
from orket.runtime.provider_truth_table import provider_truth_table_snapshot
from orket.runtime.run_phase_contract import run_phase_contract_snapshot
from orket.runtime.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
)
from orket.runtime.state_transition_registry import state_transition_registry_snapshot
from orket.runtime.timeout_streaming_contracts import (
    streaming_semantics_snapshot,
    timeout_semantics_snapshot,
)
from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from orket.runtime.runtime_invariant_registry import runtime_invariant_registry_snapshot
from orket.runtime.runtime_truth_trace_ids import runtime_truth_trace_ids_snapshot
from orket.runtime.workspace_snapshot import capture_workspace_state_snapshot
from orket.utils import sanitize_name

_DETERMINISM_RANK = {
    "pure": 0,
    "workspace": 1,
    "external": 2,
}


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
    runtime_root = workspace / "observability" / sanitize_name(resolved_run_id) / "runtime_contracts"
    runtime_root.mkdir(parents=True, exist_ok=True)

    snapshot_paths = write_runtime_contract_snapshots(
        snapshots=contract_snapshots,
        output_dir=runtime_root,
    )

    run_identity_path = runtime_root / "run_identity.json"
    run_identity = _resolve_run_identity(
        path=run_identity_path,
        run_id=resolved_run_id,
        workload=resolved_workload,
        now=now,
    )

    run_phase_contract = run_phase_contract_snapshot()
    run_phase_contract_path = runtime_root / "run_phase_contract.json"
    _write_immutable_json(
        path=run_phase_contract_path,
        payload=run_phase_contract,
        error_code="E_RUN_PHASE_CONTRACT_IMMUTABLE",
    )

    runtime_status_vocabulary = runtime_status_vocabulary_snapshot()
    runtime_status_vocabulary_path = runtime_root / "runtime_status_vocabulary.json"
    _write_immutable_json(
        path=runtime_status_vocabulary_path,
        payload=runtime_status_vocabulary,
        error_code="E_RUN_STATUS_VOCABULARY_IMMUTABLE",
    )

    degradation_taxonomy = degradation_taxonomy_snapshot()
    degradation_taxonomy_path = runtime_root / "degradation_taxonomy.json"
    _write_immutable_json(
        path=degradation_taxonomy_path,
        payload=degradation_taxonomy,
        error_code="E_RUN_DEGRADATION_TAXONOMY_IMMUTABLE",
    )

    fail_behavior_registry = fail_behavior_registry_snapshot()
    fail_behavior_registry_path = runtime_root / "fail_behavior_registry.json"
    _write_immutable_json(
        path=fail_behavior_registry_path,
        payload=fail_behavior_registry,
        error_code="E_RUN_FAIL_BEHAVIOR_REGISTRY_IMMUTABLE",
    )

    provider_truth_table = provider_truth_table_snapshot()
    provider_truth_table_path = runtime_root / "provider_truth_table.json"
    _write_immutable_json(
        path=provider_truth_table_path,
        payload=provider_truth_table,
        error_code="E_RUN_PROVIDER_TRUTH_TABLE_IMMUTABLE",
    )

    state_transition_registry = state_transition_registry_snapshot()
    state_transition_registry_path = runtime_root / "state_transition_registry.json"
    _write_immutable_json(
        path=state_transition_registry_path,
        payload=state_transition_registry,
        error_code="E_RUN_STATE_TRANSITION_REGISTRY_IMMUTABLE",
    )

    timeout_semantics = timeout_semantics_snapshot()
    timeout_semantics_path = runtime_root / "timeout_semantics_contract.json"
    _write_immutable_json(
        path=timeout_semantics_path,
        payload=timeout_semantics,
        error_code="E_RUN_TIMEOUT_SEMANTICS_IMMUTABLE",
    )

    streaming_semantics = streaming_semantics_snapshot()
    streaming_semantics_path = runtime_root / "streaming_semantics_contract.json"
    _write_immutable_json(
        path=streaming_semantics_path,
        payload=streaming_semantics,
        error_code="E_RUN_STREAMING_SEMANTICS_IMMUTABLE",
    )

    runtime_truth_drift_report = runtime_truth_contract_drift_report()
    if not bool(runtime_truth_drift_report.get("ok")):
        raise ValueError("E_RUN_TRUTH_CONTRACT_DRIFT")
    runtime_truth_drift_report_path = runtime_root / "runtime_truth_contract_drift_report.json"
    _write_immutable_json(
        path=runtime_truth_drift_report_path,
        payload=runtime_truth_drift_report,
        error_code="E_RUN_TRUTH_CONTRACT_DRIFT_REPORT_IMMUTABLE",
    )

    runtime_truth_trace_ids = runtime_truth_trace_ids_snapshot()
    runtime_truth_trace_ids_path = runtime_root / "runtime_truth_trace_ids.json"
    _write_immutable_json(
        path=runtime_truth_trace_ids_path,
        payload=runtime_truth_trace_ids,
        error_code="E_RUN_TRUTH_TRACE_IDS_IMMUTABLE",
    )

    runtime_invariant_registry = runtime_invariant_registry_snapshot()
    runtime_invariant_registry_path = runtime_root / "runtime_invariant_registry.json"
    _write_immutable_json(
        path=runtime_invariant_registry_path,
        payload=runtime_invariant_registry,
        error_code="E_RUN_INVARIANT_REGISTRY_IMMUTABLE",
    )

    ledger_event_schema = _ledger_event_schema_payload()
    ledger_event_schema_path = runtime_root / "ledger_event_schema.json"
    _write_immutable_json(
        path=ledger_event_schema_path,
        payload=ledger_event_schema,
        error_code="E_RUN_LEDGER_EVENT_SCHEMA_IMMUTABLE",
    )

    capability_manifest_schema = _capability_manifest_schema_payload()
    capability_manifest_schema_path = runtime_root / "capability_manifest_schema.json"
    _write_immutable_json(
        path=capability_manifest_schema_path,
        payload=capability_manifest_schema,
        error_code="E_RUN_CAPABILITY_MANIFEST_SCHEMA_IMMUTABLE",
    )

    capability_manifest = _capability_manifest_payload(
        run_id=resolved_run_id,
        snapshots=contract_snapshots,
    )
    capability_manifest_path = runtime_root / "capability_manifest.json"
    _write_immutable_json(
        path=capability_manifest_path,
        payload=capability_manifest,
        error_code="E_RUN_CAPABILITY_MANIFEST_IMMUTABLE",
    )
    workspace_state_snapshot_path = runtime_root / "workspace_state_snapshot.json"
    workspace_state_snapshot = _resolve_workspace_state_snapshot(
        path=workspace_state_snapshot_path,
        workspace=workspace,
        now=now,
    )

    return {
        **contract_snapshots.as_ledger_artifacts(),
        **snapshot_paths,
        "run_identity": run_identity,
        "run_identity_path": str(run_identity_path),
        "run_phase_contract": run_phase_contract,
        "run_phase_contract_path": str(run_phase_contract_path),
        "runtime_status_vocabulary": runtime_status_vocabulary,
        "runtime_status_vocabulary_path": str(runtime_status_vocabulary_path),
        "degradation_taxonomy": degradation_taxonomy,
        "degradation_taxonomy_path": str(degradation_taxonomy_path),
        "fail_behavior_registry": fail_behavior_registry,
        "fail_behavior_registry_path": str(fail_behavior_registry_path),
        "provider_truth_table": provider_truth_table,
        "provider_truth_table_path": str(provider_truth_table_path),
        "state_transition_registry": state_transition_registry,
        "state_transition_registry_path": str(state_transition_registry_path),
        "timeout_semantics_contract": timeout_semantics,
        "timeout_semantics_contract_path": str(timeout_semantics_path),
        "streaming_semantics_contract": streaming_semantics,
        "streaming_semantics_contract_path": str(streaming_semantics_path),
        "runtime_truth_contract_drift_report": runtime_truth_drift_report,
        "runtime_truth_contract_drift_report_path": str(runtime_truth_drift_report_path),
        "runtime_truth_trace_ids": runtime_truth_trace_ids,
        "runtime_truth_trace_ids_path": str(runtime_truth_trace_ids_path),
        "runtime_invariant_registry": runtime_invariant_registry,
        "runtime_invariant_registry_path": str(runtime_invariant_registry_path),
        "ledger_event_schema": ledger_event_schema,
        "ledger_event_schema_path": str(ledger_event_schema_path),
        "capability_manifest_schema": capability_manifest_schema,
        "capability_manifest_schema_path": str(capability_manifest_schema_path),
        "capability_manifest": capability_manifest,
        "capability_manifest_path": str(capability_manifest_path),
        "workspace_state_snapshot": workspace_state_snapshot,
        "workspace_state_snapshot_path": str(workspace_state_snapshot_path),
        "run_determinism_class": capability_manifest["run_determinism_class"],
    }


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
) -> dict[str, str]:
    existing = _load_json_dict(path)
    if existing is not None:
        existing_run_id = str(existing.get("run_id") or "").strip()
        existing_workload = str(existing.get("workload") or "").strip()
        existing_start = str(existing.get("start_time") or "").strip()
        if existing_run_id != run_id:
            raise ValueError("E_RUN_IDENTITY_IMMUTABLE:run_id_mismatch")
        if existing_workload != workload:
            raise ValueError("E_RUN_IDENTITY_IMMUTABLE:workload_mismatch")
        if not existing_start:
            raise ValueError("E_RUN_IDENTITY_SCHEMA:start_time_required")
        return {
            "run_id": existing_run_id,
            "workload": existing_workload,
            "start_time": existing_start,
        }

    start_time = (now or datetime.now(UTC)).isoformat()
    payload = {
        "run_id": run_id,
        "workload": workload,
        "start_time": start_time,
    }
    _write_json(path, payload)
    return payload


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


def _ledger_event_schema_payload() -> dict[str, Any]:
    return {
        "ledger_schema_version": "1.0",
        "event_type": "tool_call|tool_result|run_started|run_finalized",
        "required_fields": [
            "ledger_schema_version",
            "event_type",
            "timestamp",
            "tool_name",
            "run_id",
            "sequence_number",
        ],
        "required_on_tool_result": [
            "call_sequence_number",
            "tool_call_hash",
        ],
        "required_on_artifact_reference": [
            "artifact_hash",
        ],
    }


def _capability_manifest_schema_payload() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "type": "object",
        "required": [
            "run_id",
            "capabilities_allowed",
            "capabilities_used",
            "run_determinism_class",
        ],
        "properties": {
            "run_id": {"type": "string", "min_length": 1},
            "capabilities_allowed": {"type": "array", "items": {"type": "string"}},
            "capabilities_used": {"type": "array", "items": {"type": "string"}},
            "run_determinism_class": {"type": "string", "enum": ["pure", "workspace", "external"]},
        },
    }


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
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json_dict(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"E_RUN_ARTIFACT_PARSE:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"E_RUN_ARTIFACT_SCHEMA:{path}:root payload must be object")
    return dict(payload)
