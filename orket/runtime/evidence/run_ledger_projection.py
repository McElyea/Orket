from __future__ import annotations

import json
from typing import Any


def coerce_run_ledger_json_object(payload: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(payload, dict):
        return dict(payload), True
    text = str(payload or "").strip()
    if not text:
        return {}, False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}, False
    if not isinstance(parsed, dict):
        return {}, False
    return dict(parsed), True


def _run_ledger_payload_missing(payload: Any) -> bool:
    if payload is None:
        return True
    if isinstance(payload, str):
        return not payload.strip()
    return False


def project_run_ledger_summary(summary_payload: Any) -> tuple[dict[str, Any], bool]:
    if _run_ledger_payload_missing(summary_payload):
        return {}, True
    summary, is_json_object = coerce_run_ledger_json_object(summary_payload)
    if not is_json_object:
        return {}, False
    return summary, True


def project_run_ledger_artifacts(artifacts_payload: Any) -> tuple[dict[str, Any], bool]:
    if _run_ledger_payload_missing(artifacts_payload):
        return {}, True
    artifacts, is_json_object = coerce_run_ledger_json_object(artifacts_payload)
    if not is_json_object:
        return {}, False
    return artifacts, True


def project_run_ledger_record(run_record: Any) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(run_record, dict):
        return None, []

    projected = dict(run_record)
    summary, summary_valid = project_run_ledger_summary(run_record.get("summary_json"))
    artifacts, artifacts_valid = project_run_ledger_artifacts(run_record.get("artifact_json"))
    projected["summary_json"] = summary
    projected["artifact_json"] = artifacts

    invalid_projection_fields: list[str] = []
    if not summary_valid:
        invalid_projection_fields.append("summary_json")
    if not artifacts_valid:
        invalid_projection_fields.append("artifact_json")
    return projected, invalid_projection_fields


__all__ = [
    "coerce_run_ledger_json_object",
    "project_run_ledger_artifacts",
    "project_run_ledger_record",
    "project_run_ledger_summary",
]
