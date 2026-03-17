from __future__ import annotations

from typing import Any

from .validator import (
    authorize_tool_call_v1,
    compare_runs_v1,
    execute_turn_v1,
    finish_run_v1,
    replay_run_v1,
    resolve_capability_v1,
    start_run_v1,
)
from .nervous_system_runtime import (
    admit_proposal_v1,
    commit_proposal_v1,
    end_session_v1,
    projection_pack_v1,
)
from .nervous_system_runtime_extensions import (
    audit_action_lifecycle_v1,
    list_ledger_events_v1,
    rebuild_pending_approvals_v1,
    replay_action_lifecycle_v1,
)
from .nervous_system_runtime_state import get_str
from .experiments.runner import run_experiment_v1


def start_run(request: dict[str, Any]) -> dict[str, Any]:
    return start_run_v1(request)


def execute_turn(request: dict[str, Any]) -> dict[str, Any]:
    return execute_turn_v1(request)


def finish_run(request: dict[str, Any]) -> dict[str, Any]:
    return finish_run_v1(request)


def resolve_capability(request: dict[str, Any]) -> dict[str, Any]:
    return resolve_capability_v1(request)


def authorize_tool_call(request: dict[str, Any]) -> dict[str, Any]:
    return authorize_tool_call_v1(request)


def replay_run(request: dict[str, Any]) -> dict[str, Any]:
    return replay_run_v1(request)


def compare_runs(request: dict[str, Any]) -> dict[str, Any]:
    return compare_runs_v1(request)


def projection_pack(request: dict[str, Any]) -> dict[str, Any]:
    return projection_pack_v1(request)


def admit_proposal(request: dict[str, Any]) -> dict[str, Any]:
    return admit_proposal_v1(request)


def commit_proposal(request: dict[str, Any]) -> dict[str, Any]:
    return commit_proposal_v1(request)


def end_session(request: dict[str, Any]) -> dict[str, Any]:
    return end_session_v1(request)


def list_ledger_events(request: dict[str, Any]) -> dict[str, Any]:
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=False)
    event_type = get_str(request, "event_type", required=False)
    limit = int(request.get("limit") or 200)
    items = list_ledger_events_v1(
        session_id=session_id,
        trace_id=trace_id,
        event_type=event_type,
        limit=limit,
    )
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "event_type": event_type,
        "items": items,
        "count": len(items),
    }


def rebuild_pending_approvals(request: dict[str, Any]) -> dict[str, Any]:
    session_id = get_str(request, "session_id", required=True)
    items = rebuild_pending_approvals_v1(session_id)
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "items": items,
        "count": len(items),
    }


def replay_action_lifecycle(request: dict[str, Any]) -> dict[str, Any]:
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    return replay_action_lifecycle_v1(session_id=session_id, trace_id=trace_id)


def audit_action_lifecycle(request: dict[str, Any]) -> dict[str, Any]:
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    return audit_action_lifecycle_v1(session_id=session_id, trace_id=trace_id)


def run_experiment(request: dict[str, Any]) -> dict[str, Any]:
    return run_experiment_v1(request)


__all__ = [
    "audit_action_lifecycle",
    "authorize_tool_call",
    "compare_runs",
    "projection_pack",
    "admit_proposal",
    "commit_proposal",
    "end_session",
    "execute_turn",
    "finish_run",
    "list_ledger_events",
    "replay_run",
    "replay_action_lifecycle",
    "rebuild_pending_approvals",
    "resolve_capability",
    "run_experiment",
    "start_run",
]
