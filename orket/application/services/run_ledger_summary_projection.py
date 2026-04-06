from __future__ import annotations

from typing import Any

from orket.runtime.run_ledger_projection import (
    project_run_ledger_artifacts,
    project_run_ledger_record,
    project_run_ledger_summary,
)
from orket.runtime.run_summary import validate_run_summary_payload


def validated_run_ledger_summary(summary_payload: Any) -> dict[str, Any]:
    summary, is_valid = project_run_ledger_summary(summary_payload)
    if not is_valid:
        return {}
    try:
        validate_run_summary_payload(summary)
    except ValueError:
        return {}
    return summary


def validated_run_ledger_artifacts(artifacts_payload: Any) -> dict[str, Any]:
    return project_run_ledger_artifacts(artifacts_payload)[0]


def validated_run_ledger_record_projection(run_record: Any) -> dict[str, Any] | None:
    projected, _ = project_run_ledger_record(run_record)
    if projected is None:
        return None
    projected["summary_json"] = validated_run_ledger_summary(projected.get("summary_json"))
    projected["artifact_json"] = validated_run_ledger_artifacts(projected.get("artifact_json"))
    return projected
