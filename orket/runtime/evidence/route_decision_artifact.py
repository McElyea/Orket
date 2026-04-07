from __future__ import annotations

from typing import Any

ROUTE_DECISION_ARTIFACT_SCHEMA_VERSION = "1.0"


def build_route_decision_artifact(
    *,
    run_id: str,
    workload_kind: str,
    execution_runtime_node: Any,
    pipeline_wiring_node: Any,
    target_issue_id: str | None,
    resume_mode: bool,
    deterministic_mode_enabled: bool,
) -> dict[str, object]:
    target_issue = str(target_issue_id or "").strip() or None
    reason_code = "default_epic_route"
    if target_issue:
        reason_code = "target_issue_override"
    elif bool(resume_mode):
        reason_code = "resume_stalled_issues"

    return {
        "schema_version": ROUTE_DECISION_ARTIFACT_SCHEMA_VERSION,
        "run_id": str(run_id or "").strip(),
        "workload_kind": str(workload_kind or "").strip() or "unknown",
        "route_target": "epic" if not target_issue else "issue",
        "target_issue_id": target_issue,
        "resume_mode": bool(resume_mode),
        "reason_code": reason_code,
        "deterministic_mode_enabled": bool(deterministic_mode_enabled),
        "decision_nodes": {
            "execution_runtime_node": type(execution_runtime_node).__name__,
            "pipeline_wiring_node": type(pipeline_wiring_node).__name__,
        },
    }
