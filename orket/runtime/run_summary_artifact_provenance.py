from __future__ import annotations

from datetime import datetime
from typing import Any

ARTIFACT_PROVENANCE_KEY = "truthful_runtime_artifact_provenance"
ARTIFACT_PROVENANCE_SCHEMA_VERSION = "1.0"
_ALLOWED_TRUTH_CLASSIFICATIONS = {"direct", "inferred", "estimated", "repaired", "degraded"}


def build_artifact_provenance_extension(*, artifacts: dict[str, Any]) -> dict[str, Any] | None:
    facts = normalize_artifact_provenance_facts(artifacts.get("artifact_provenance_facts"))
    entries = list(facts.get("artifacts") or [])
    if not entries:
        return None
    return {
        "schema_version": ARTIFACT_PROVENANCE_SCHEMA_VERSION,
        "projection_source": "artifact_provenance_facts",
        "projection_only": True,
        "artifacts": entries,
    }


def normalize_artifact_provenance_facts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    entries = _normalize_entries(value.get("artifacts"))
    if not entries:
        return {}
    return {"artifacts": entries}


def _normalize_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    deduped: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        artifact_path = str(item.get("artifact_path") or "").strip()
        artifact_type = str(item.get("artifact_type") or "").strip()
        generator = str(item.get("generator") or "").strip()
        generator_version = str(item.get("generator_version") or "").strip()
        source_hash = str(item.get("source_hash") or "").strip()
        produced_at = _normalize_iso8601(item.get("produced_at"))
        truth_classification = str(item.get("truth_classification") or "").strip()
        if not (
            artifact_path
            and artifact_type
            and generator
            and generator_version
            and source_hash
            and produced_at
            and truth_classification in _ALLOWED_TRUTH_CLASSIFICATIONS
        ):
            continue
        entry = {
            "artifact_path": artifact_path,
            "artifact_type": artifact_type,
            "generator": generator,
            "generator_version": generator_version,
            "source_hash": source_hash,
            "produced_at": produced_at,
            "truth_classification": truth_classification,
        }
        step_id = str(item.get("step_id") or "").strip()
        if step_id:
            entry["step_id"] = step_id
        operation_id = str(item.get("operation_id") or "").strip()
        if operation_id:
            entry["operation_id"] = operation_id
        issue_id = str(item.get("issue_id") or "").strip()
        if issue_id:
            entry["issue_id"] = issue_id
        role_name = str(item.get("role_name") or "").strip()
        if role_name:
            entry["role_name"] = role_name
        turn_index = _normalize_turn_index(item.get("turn_index"))
        if turn_index > 0:
            entry["turn_index"] = turn_index
        control_plane_run_id = str(item.get("control_plane_run_id") or "").strip()
        if control_plane_run_id:
            entry["control_plane_run_id"] = control_plane_run_id
        control_plane_attempt_id = str(item.get("control_plane_attempt_id") or "").strip()
        if control_plane_attempt_id:
            entry["control_plane_attempt_id"] = control_plane_attempt_id
        control_plane_step_id = str(item.get("control_plane_step_id") or "").strip()
        if control_plane_step_id:
            entry["control_plane_step_id"] = control_plane_step_id
        tool_call_hash = str(item.get("tool_call_hash") or "").strip()
        if tool_call_hash:
            entry["tool_call_hash"] = tool_call_hash
        receipt_digest = str(item.get("receipt_digest") or "").strip()
        if receipt_digest:
            entry["receipt_digest"] = receipt_digest
        deduped[artifact_path] = entry
    return [deduped[key] for key in sorted(deduped)]


def _normalize_iso8601(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return ""
    return parsed.isoformat()


def _normalize_turn_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0
