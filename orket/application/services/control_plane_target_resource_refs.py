from __future__ import annotations

from typing import Any

from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    resource_id_for_run as kernel_action_resource_id_for_run,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    namespace_resource_id,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    resource_id as orchestrator_issue_dispatch_resource_id,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    namespace_resource_id_for_run,
)


def resource_id_for_supported_run(*, run: Any) -> str | None:
    run_id = str(getattr(run, "run_id", "") or "").strip()
    if run_id.startswith("turn-tool-run:"):
        try:
            return namespace_resource_id_for_run(run=run)
        except ValueError:
            return None
    if run_id.startswith("kernel-action-run:"):
        return kernel_action_resource_id_for_run(run=run)
    if run_id.startswith("orchestrator-issue-run:"):
        session_issue = _orchestrator_issue_dispatch_target(run_id=run_id)
        if session_issue is None:
            return None
        session_id, issue_id = session_issue
        return orchestrator_issue_dispatch_resource_id(session_id=session_id, issue_id=issue_id)
    if run_id.startswith("orchestrator-issue-scheduler-run:") or run_id.startswith("orchestrator-child-workload-run:"):
        return _namespace_resource_id_from_run(run=run)
    return None


def _namespace_resource_id_from_run(*, run: Any) -> str | None:
    namespace_scope = str(getattr(run, "namespace_scope", "") or "").strip()
    prefix = "issue:"
    if not namespace_scope.startswith(prefix):
        return None
    issue_id = namespace_scope[len(prefix) :].strip()
    if not issue_id:
        return None
    return namespace_resource_id(issue_id=issue_id)


def _orchestrator_issue_dispatch_target(*, run_id: str) -> tuple[str, str] | None:
    prefix = "orchestrator-issue-run:"
    suffix = str(run_id or "").strip()
    if not suffix.startswith(prefix):
        return None
    parts = suffix[len(prefix) :].split(":")
    if len(parts) < 4:
        return None
    session_id = str(parts[0] or "").strip()
    issue_id = str(parts[1] or "").strip()
    if not session_id or not issue_id:
        return None
    return session_id, issue_id


__all__ = ["resource_id_for_supported_run"]
